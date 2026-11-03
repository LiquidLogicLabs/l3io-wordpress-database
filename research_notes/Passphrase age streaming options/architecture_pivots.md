# Architecture pivots avoiding pyrage passphrase streaming

Research date: 2026-10-25. Scope: non-`encrypt_io` designs that still serve WordPress backup/database needs (multi-GB streams, operator recovery, shared format with backup). Project context from ADR-0003 and plan-4; external facts from age C2SP, FiloSottile materials, backup-tool designs.

## Can we generate a random file key, encrypt the stream to that X25519 recipient via existing pyrage.encrypt_io, and wrap the private key with passphrase.encrypt — as ONE stock-age file?

### Takeaway
That workflow works as **two** standard age artifacts (stream ciphertext + passphrase-wrapped identity), not as one stock-`age -d`-recoverable file; packing them into a custom container or mixing scrypt+X25519 stanzas breaks stock age recoverability and/or the age spec.

### Cited Findings
- Age already wraps a random 16-byte file key once per recipient stanza, then STREAM-encrypts the payload; X25519 and scrypt are two ways to wrap that same file key — [age v1 format (C2SP)](https://c2sp.org/age); [age-encryption.org/v1](https://age-encryption.org/v1).
- An scrypt stanza, if present, **MUST be the only stanza** in the header; scrypt may not be mixed with X25519 or other types — [age v1 format (C2SP)](https://c2sp.org/age); [age-encryption.org/v1](https://age-encryption.org/v1).
- FiloSottile’s Go API documents the same rule: `ScryptRecipient` must be the only recipient; mixing breaks the user’s expectation that a passphrase both decrypts and authenticates the file — [filippo.io/age scrypt.go](https://github.com/FiloSottile/age/blob/main/scrypt.go); [age authentication dispatch](https://words.filippo.io/dispatches/age-authentication/).
- pyrage already exposes streaming recipient IO (`encrypt_io` / `decrypt_io`) and only one-shot passphrase APIs that take/return `bytes` — [woodruffw/pyrage README](https://github.com/woodruffw/pyrage); [pyrage design post](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage); [woodruffw/pyrage#172](https://github.com/woodruffw/pyrage/issues/172).
- Official CLI pattern for “passphrase protects a small key, recipients encrypt the large file” is: `age-keygen | age -p > key.age`, then `age -r <pubkey> …`, then `age -d -i key.age …` — [FiloSottile/age README](https://github.com/FiloSottile/age); [age(1) man page](https://man.archlinux.org/man/age.1.en).
- Plan-4 / ADR-0003 require stock `age -d` recovery for passphrase mode with a **sole scrypt recipient**, and reject hand-rolled scrypt+STREAM — [docs/adr/0003-age-encryption.md](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/adr/0003-age-encryption.md); [plan-4](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/_bmad-output/planning-artifacts/plans/2026-10-20-plan-4-passphrase-stream.md).
- Hand-rolling a second layer that wraps “the content key” outside age’s header (custom prefix, tar sidecar, JSON envelope) produces a format that stock `age -d` cannot open as a single input — inferred from age format being header+STREAM only — [age v1 format (C2SP)](https://c2sp.org/age).

### Inferences
- **Viable stock-compatible hybrid:** generate an ephemeral or durable X25519 identity; `encrypt_io` the multi-GB dump/archive to that recipient; `passphrase.encrypt` (buffered) only the small identity bytes. Operator recovery: `age -d -i identity.age dump.age` (passphrase prompts for the identity file). This is **not** one-file `age -d dump.age`.
- **Not viable as one age file:** embedding a passphrase-wrapped private key *inside* the same age ciphertext as a second recipient stanza (scrypt + X25519) is rejected by implementations and the spec.
- **Footgun — “wrap the age file key yourself”:** re-implementing stanza wrapping / STREAM outside pyrage duplicates age crypto (fixed nonce on wrap AEAD, salt/work-factor rules, STREAM chunk nonces). ADR-0003 already rejected hand-rolled scrypt+STREAM for this reason.
- **Footgun — custom “one file” container:** `tar`/`cat` of `key.age` + `data.age` is recoverable only with a documented unpack protocol; operators cannot `age -d backup.bin` alone. That breaks the “operator recovery without this package” goal unless backup AD-26 explicitly accepts a two-step recovery UX.
- Calling the private key a “content key” is slightly misleading: age’s content/file key is already 16 random bytes inside the age header; the X25519 identity is a *recipient* key that unwraps it.

### Gaps
- No public citation found that any major tool ships a single stock-age file combining passphrase unwrap of an embedded X25519 identity *inside* one age header (because the spec forbids it).
- Exact backup AD-26 wording lives in `l3io-wordpress-backup` (not this repo); this note uses handoff/plan-4 references only.

## Age “identity encrypted with passphrase” workflow: generate identity, passphrase-encrypt identity (small), stream recipient-encrypt the dump — operator recovery?

### Takeaway
This is a **first-class, documented age workflow**; it already fits ADR-0003’s recipients/identities mode and avoids needing `passphrase.encrypt_io` for multi-GB data. Stock recovery uses `age -d -i`, not bare `age -d`.

### Cited Findings
- Passphrase-protected identity files: `age-keygen | age -p > key.age`; encrypt with public recipient; decrypt with `-i key.age` (CLI prompts for identity passphrase) — [FiloSottile/age README](https://github.com/FiloSottile/age); [age(1)](https://man.archlinux.org/man/age.1.en).
- Encrypted identity files must themselves be passphrase/scrypt-encrypted age files; max size ~16 MiB; CLI feature (library does not auto-unwrap) — [Encrypted Identity Files (DeepWiki summary of FiloSottile/age)](https://deepwiki.com/FiloSottile/age/4.5-encrypted-identity-files); [age v1.0.0-rc.3 release notes](https://github.com/FiloSottile/age/releases/tag/v1.0.0-rc.3).
- Removing passphrase protection is `age -d -o key.txt key.age` then discard `key.age` — [FiloSottile/age Discussion #693](https://github.com/FiloSottile/age/discussions/693).
- ADR-0003 already states identities “may themselves be passphrase-protected on the small identity file,” separate from content `passphrase=` mode — [docs/adr/0003-age-encryption.md](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/adr/0003-age-encryption.md).
- Design spec §7.3: identity may be passphrase-protected using age passphrase mode on the small identity file; content passphrase mode is a distinct sole-scrypt path — [design spec](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/_bmad-output/planning-artifacts/spec/2026-10-12-l3io-wordpress-database-design.md).
- ScryptRecipient “is not recommended for automated systems, which should prefer … X25519Recipient” — [filippo.io/age ScryptRecipient docs](https://pkg.go.dev/filippo.io/age); [scrypt.go](https://github.com/FiloSottile/age/blob/main/scrypt.go).
- pyrage passphrase path buffers whole plaintext; identity files are tiny (one Bech32 secret line), so buffered `passphrase.encrypt` / `decrypt` is appropriate for the identity only — [pyrage README](https://github.com/woodruffw/pyrage); [pyrage#172](https://github.com/woodruffw/pyrage/issues/172).

### Inferences
- **Operator recovery path (stock age):** keep `identity.age` (or operator’s durable key) alongside the dump/archive; run `age -d -i identity.age dump.age`. Passphrase never touches the multi-GB STREAM path in Python.
- **Package API fit today:** `dump(..., recipients=[pubkey])` + manage identity out-of-band (backup AD-26 chain holds passphrase for identity unwrap, or operator stores plaintext identity offline). No upstream pyrage change required for the large stream.
- **UX difference vs plan-4 passphrase=:** operators do **not** recover with only `age -d` + passphrase on the dump; they need the identity artifact. Plan-4’s accepted design targeted sole-scrypt dumps so `age -d` alone works — [plan-4](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/_bmad-output/planning-artifacts/plans/2026-10-20-plan-4-passphrase-stream.md).
- **Per-backup ephemeral identity:** generating a new identity per dump and wrapping it with the operator passphrase yields “passphrase recovers dump” only if the wrapped identity is stored/distributed with the dump (two files or custom bundle). Same packaging tradeoff as Q1.
- **Footgun:** decrypting identity into a long-lived tempfile on disk; prefer in-memory unwrap then pass identity string to `decrypt_io`. Footgun: treating passphrase-wrapped identity as if content were passphrase-encrypted (wrong API, wrong operator docs).

### Gaps
- Whether backup AD-26 already assumes sole-scrypt archives vs passphrase-wrapped identity is not verifiable from this repo alone.
- pyrage Python API support for feeding already-unwrapped identity bytes vs CLI-style encrypted identity files needs local API confirmation (not re-fetched in this pass).

## Does age support multiple recipients including scrypt + x25519 in one file, and would that help?

### Takeaway
No: scrypt must be alone. Multiple **X25519** (and SSH) recipients are fine; mixing scrypt with them is forbidden and would not safely deliver “passphrase or key” dual recovery in one stock file.

### Cited Findings
- Multiple recipients via repeated `-r` / `-R`; every listed recipient can decrypt — [FiloSottile/age README](https://github.com/FiloSottile/age).
- scrypt sole-stanza rule and MUST-reject on decrypt if mixed — [C2SP age](https://c2sp.org/age); [age-encryption.org/v1](https://age-encryption.org/v1).
- Rationale: passphrase users expect authentication; other recipients could forge ciphertexts that still decrypt under the passphrase — [scrypt.go WrapWithLabels comment](https://github.com/FiloSottile/age/blob/main/scrypt.go); [age authentication article](https://words.filippo.io/dispatches/age-authentication/); [Discussion #613](https://github.com/FiloSottile/age/discussions/613).
- CLI: `--passphrase` cannot be used with other recipient flags — [age(1)](https://man.archlinux.org/man/age.1.en).
- Plan-4 “Out of scope”: combining passphrase with recipients is forbidden by age; refuse loudly — [plan-4](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/_bmad-output/planning-artifacts/plans/2026-10-20-plan-4-passphrase-stream.md).

### Inferences
- Dual recovery (ops team X25519 **or** human passphrase) requires **two separate age files**, or two copies of the payload, or a non-age envelope — not one compliant age header.
- Multiple X25519 recipients **do** help shared-format multi-operator recovery without passphrase streaming.
- Attempting to “help” by emitting non-compliant mixed headers would fail stock `age -d` and rage/pyrage decrypt.

### Gaps
- None material for the binary yes/no; plugin recipient types that mimic passphrase semantics were not surveyed beyond native scrypt/X25519.

## Chunked age files / age boxes / tar-of-encrypted-chunks patterns

### Takeaway
Native age already chunk-STREAM-encrypts payloads (64 KiB); “agebox” and “many small `.age` files” solve repo/secret workflows, not one multi-GB dump. Custom tar-of-age-chunks is a new format and loses single-file `age -d`.

### Cited Findings
- Age payload uses STREAM: fixed 64 KiB plaintext chunks, ChaCha20-Poly1305, incrementing nonces, final-chunk flag; enables streaming and bounded memory — [Stream Encryption (DeepWiki / FiloSottile/age internals)](https://deepwiki.com/FiloSottile/age/3.3-stream-encryption); [age(1) overhead note: ~16 bytes / 64KiB](https://man.archlinux.org/man/age.1.en).
- **agebox** encrypts individual repository files with age recipients, tracks them in `.ageboxreg.yml`; GitOps/secrets focus, not streaming database dumps — [slok/agebox](https://github.com/slok/agebox/).
- **aerback**: tar → age (recipients file) → rclone; whole-archive age file, recipient-oriented — [lukasdietrich/aerback](https://github.com/lukasdietrich/aerback).
- **vaultik** (design): content-defined chunks packed into encrypted age blobs; metadata also age-encrypted; asymmetric/public-key on source host — [vaultik design commit](https://git.eeqj.de/sneak/vaultik/commit/417b25a5f5bbc57752f6fa173d11ff8e81341724).
- **age-rt**: variable-length chunk protocol with age-like header; passphrase streaming; **not** identical to stock age v1 fixed chunks; length patterns leak; author warns not independently reviewed — [parsimonit/python-age-rt](https://github.com/parsimonit/python-age-rt).

### Inferences
- For this package, “chunked encryption” is already inside `encrypt_io` once a file key exists; splitting a dump into N age files only helps if each chunk is small enough for buffered passphrase.encrypt — at multi-GB scale that means thousands of scrypt operations (CPU DoS / UX disaster) or abandoning passphrase per chunk.
- Tar-of-encrypted-chunks: stock recovery becomes “untar then age -d each member” or a custom tool; conflicts with ADR-0003 “any dump decrypts with the stock age command line” as a **single** invocation unless the tar contains one age member.
- **Footguns:** hand-rolled chunk AEAD with reused nonces; missing final-chunk authentication (truncation); inconsistent per-chunk recipients; scrypt per chunk.

### Gaps
- No evidence of a widely deployed “tar of age chunks + one passphrase sidecar” standard compatible with stock age alone.
- Backup AD-21 peak-RSS constraints on multi-file layouts not measured here.

## Accepting buffered passphrase only for small artifacts; recipients required for multi-GB

### Takeaway
This is the lowest-risk pivot relative to pyrage upstream friction: keep `passphrase.encrypt` for identity/key material; require `recipients=` (streaming) for dumps/archives ≥ memory budget; optionally defer or narrow content-`passphrase=` in 0.2.0.

### Cited Findings
- Maintainer signal on pyrage#172: reluctant to add more streaming APIs (“hard to get right”); wants clearer problem framing — [woodruffw/pyrage#172](https://github.com/woodruffw/pyrage/issues/172) (2026-10-21).
- Plan-4 rejected buffering whole payloads via `passphrase.encrypt` for archives/dumps; rejected age CLI subprocess for passphrase (TTY / no safe argv channel) — [plan-4](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/_bmad-output/planning-artifacts/plans/2026-10-20-plan-4-passphrase-stream.md).
- Kassiber abandoned safe age-CLI passphrase subprocess and fell back to buffering pyrage for passphrase mode — [kassiber age_cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/age_cli.py).
- Age authors recommend X25519 over scrypt for automated systems — [pkg.go.dev/filippo.io/age](https://pkg.go.dev/filippo.io/age).
- ADR-0003 amendment and handoff currently commit 0.2.0 to streaming content passphrase via `encrypt_io` / `decrypt_io` and sole scrypt — [ADR-0003](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/adr/0003-age-encryption.md); [handoff](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/handoff/wordpress-database.md).

### Inferences
- **Policy pivot:** document hard limit (e.g. refuse `passphrase=` above N MiB / always for `dump`) and steer operators to recipients or passphrase-wrapped identity. Stock `age -d` for large files then requires `-i`.
- **0.2.0 scope cut:** ship recipients streaming only; leave content passphrase out until pyrage ships IO **or** accept identity-wrapping UX as the “passphrase story” for backup AD-26. Requires ADR-0003 / plan-4 amendment (status today claims passphrase streaming accepted).
- Still satisfies “shared age format with backup” if backup also uses age recipient files (or same two-file identity pattern).
- Does **not** satisfy plan-4’s “sole scrypt dump, `age -d` with passphrase only” without either upstream IO or buffering (rejected).

### Gaps
- Concrete N MiB threshold and whether WordPress dumps are ever “small enough” were not sized in this research.
- Shawn’s willingness to amend ADR-0003 after maintainer pushback is a product decision, not a technical finding.

## Switching format entirely (GPG, age-rt, agebox, sops, etc.): cost to ADR-0003 and backup AD-26

### Takeaway
A format switch is high cost: ADR-0003 explicitly chose age/pyrage for streaming + stock CLI recovery + no keyring; backup AD-26 is cited as sharing that age format. Alternatives either reintroduce rejected dependencies, lose stock `age -d`, or target the wrong artifact class (structured secrets, not multi-GB dumps).

### Cited Findings
- ADR-0003 rejected: GPG/`python-gnupg` (binary + keyring), Fernet (non-streaming, Python-only), hand-rolled scrypt+STREAM, age CLI subprocess for passphrase — [ADR-0003](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/adr/0003-age-encryption.md).
- Decision consequences: dumps/archives decrypt with stock `age`; backup shares format; bounded memory — [ADR-0003](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/adr/0003-age-encryption.md).
- Handoff ties streaming passphrase to backup AD-26 / AD-21 and plan-4 — [handoff](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/handoff/wordpress-database.md).
- **SOPS** wraps a data key per age recipient and encrypts structured secret values (AES-GCM), not a streaming dump pipeline — [getsops age keysource](https://github.com/getsops/sops/blob/main/age/keysource.go); [SOPS age docs](https://github.com/getsops/docs/blob/main/content/en/docs/usage/identities/age/_index.md).
- **agebox** is per-file repo encryption, not a dump format substitute — [slok/agebox](https://github.com/slok/agebox/).
- **age-rt** offers passphrase streaming but diverges from stock age v1 chunking; not a drop-in for `age -d` on variable-chunk streams — [python-age-rt](https://github.com/parsimonit/python-age-rt).
- GPG symmetric streaming exists in the broader ecosystem but reintroduces keyring/agent and binary coupling ADR-0003 rejected — [ADR-0003 options table](file:///home/ravenwolf.org/sanderson/source/git/ravensorb/wordpress/l3io-wordpress-database/docs/adr/0003-age-encryption.md).

### Inferences
- Cost to ADR-0003: supersede or rewrite; lose “stock age” operator recovery narrative; retrain operators; invalidate tests that round-trip with `age -d`.
- Cost to backup AD-26: format dual-write or break shared encrypt/decrypt imports from `l3io.wp.database`; epic coupling across packages.
- SOPS/agebox do not solve multi-GB mysqldump streams; adopting them for dumps would be misuse.
- Staying on age but changing **only** the passphrase UX (identity wrapping / recipients-only) preserves ADR-0003’s format choice while amending the passphrase-mode clause.

### Gaps
- Full text of backup AD-26 / AD-21 not in this repository; cost statements about backup are inferred from handoff/plan-4 citations.
- Comparative performance of GPG vs age for multi-GB WordPress dumps not benchmarked here.

## What restic / borg / kopia / duplicacy do for passphrase streaming (inspiration without claiming age compatibility)

### Takeaway
Those tools **do not stream-encrypt multi-GB payloads under a passphrase KDF directly**. They derive or unlock a **small key blob** from the passphrase, then encrypt content with random repository/session keys—exactly the “wrap small key, stream content” pattern. Copying that into an age-shaped world means two artifacts or a custom repo format, not sole-scrypt age files.

### Cited Findings
- **Restic:** AES-256-CTR + Poly1305-AES per blob with fresh random 16-byte nonce; repository keys derived/wrapped with scrypt; multiple key files allow password change without re-encrypting data; packs stream encrypted blobs then append encrypted header — [restic design.rst](https://github.com/restic/restic/blob/master/doc/design.rst); [restic encryption docs](https://restic.readthedocs.io/en/stable/070_encryption.html).
- **Borg:** offline key material passphrase-wrapped (Argon2 → ChaCha20-Poly1305 keyblob in Borg 2 docs path cited; PBKDF2 historically); content uses separate encryption keys/session IVs — [borg security.rst](https://github.com/borgbackup/borg/blob/86fd77fd/docs/internals/security.rst); comparative notes — [encryption-designs.md research notes](https://retoor.molodetz.nl/retoor/versioning/src/branch/master/research_notes/Backup%20encryption%20security%20choices/encryption-designs.md).
- **Kopia:** passphrase → master key via configured PBKDF; HKDF to AES/auth keys; encrypts repository format blob; content encryption separate — [Kopia encryption docs](https://kopia.io/docs/advanced/encryption/).
- **Duplicacy:** four random 256-bit keys (hash/id/chunk/file) stored in `config`, encrypted under PBKDF2-derived master key from storage password; chunks AES-GCM with keys derived from chunk hash + ChunkKey; password change rewraps config only — [Duplicacy forum encryption howto](https://forum.duplicacy.com/t/encryption-of-the-storage/1085); [duplicacy password wiki](https://github.com/gilbertchen/duplicacy/wiki/password); [GenerateKeyFromPassword](https://github.com/gilbertchen/duplicacy/blob/065ae50868574404c502fb8b9508a2475d218337/src/duplicacy_utils.go).

### Inferences
- Inspiration that **is** age-compatible: passphrase wraps identity or a small key file; large objects use X25519 (or restic-like custom crypto—but then drop age compatibility).
- Inspiration that is **not** age-compatible: inventing a “repository config” + content keys while still calling the blob `.age`.
- Age’s built-in sole-scrypt mode *does* stream content under a passphrase-derived wrap of the file key—but that is exactly the pyrage API gap (bindings buffer). Rage/age CLI already stream; the pivot options avoid depending on Python bindings for that path.
- **Footgun mapping:** restic/borg/duplicacy carefully separate KDF’d KEK from content keys and use unique nonces/IVs per blob. A naive “AES-GCM(content, scrypt(passphrase))” streaming port would invite nonce reuse and lacks age interoperability.

### Gaps
- Deep dive into Borg 2 session-key streaming code paths was secondary-sourced via security.rst / third-party notes; treat Borg 1.x vs 2 differences as approximate.
- Duplicacy RSA encryption version (`ENCRYPTION_VERSION_RSA`) not analyzed.

## Cross-cutting: stock `age -d` recoverability matrix

| Pivot | Stock recovery | Notes |
|---|---|---|
| Sole scrypt content (plan-4) | `age -d file.age` + passphrase | Needs streaming passphrase API or buffering |
| Recipients-only multi-GB | `age -d -i key.txt file.age` | Works with current `encrypt_io` |
| Passphrase-wrapped identity + recipient ciphertext | `age -d -i key.age file.age` | Two artifacts; identity small → buffered passphrase OK |
| Hybrid wrap private key + stream as **one custom file** | Not stock single `age -d` | Unpack protocol required |
| scrypt + X25519 same header | Invalid / rejected | Spec forbids |
| Tar of age chunks | Per-member `age -d` after untar | Not one-shot |
| SOPS / agebox / age-rt / GPG | Not stock age dump recovery | Format change |
| Restic-style keyblob + content keys | Custom tool | Do not claim age |

## Cross-cutting: crypto footguns to avoid

- Mixing scrypt with other recipients “to be helpful.”
- Hand-implementing STREAM / file-key wrap instead of calling pyrage/rage/age.
- Nonce/IV reuse if inventing chunk AEAD outside age.
- scrypt-per-chunk on multi-GB splits (CPU / DoS).
- Passphrase on argv or in exception messages (ADR-0003 / plan-4).
- age CLI subprocess for passphrase without a safe secret channel (plan-4 / kassiber lesson).
- Claiming “age compatible” for envelopes that stock `age -d` cannot open.
- Decrypting passphrase-wrapped identities to durable world-readable paths.

## Gaps (global)

- Backup package AD-26/AD-21 primary text not available in this workspace.
- No maintainer commitment yet that pyrage will add `passphrase.encrypt_io` (#172 open as of 2026-10-21).
- Quantitative RSS comparison of forks vs pivots not run (research-only constraint).
