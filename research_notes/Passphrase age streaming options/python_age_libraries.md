# Python age libraries for streaming passphrase encrypt/decrypt

Research date: 2026-10-25. Focus: Python 3.11+ libraries that can produce/consume stock age v1 ciphertext with passphrase (scrypt) and stream large payloads without buffering the whole dump. `woodruffw/pyrage` is the baseline comparison, not the preferred primary path for passphrase streaming.

## What packages exist: age-rt / python-age / age / pyage / others on PyPI or GitHub?

### Takeaway
The viable pure-Python age implementations on PyPI are `python-age` (dennisvink), `age-rt` (parsimonit), and the older experimental `age` package (jojonas/pyage). `pyrage` remains the mature Rust-binding option; `ssage` is a thin wrapper. Suggested `dfrankland/python-age` does not exist.

### Cited Findings
- PyPI package `python-age` v0.1.0 (Dennis Vink): “Python implementation of the age (Actually Good Encryption) v1 file format”; requires Python >=3.9; depends on `cryptography>=41.0.0`; homepage [dennisvink/python-age](https://github.com/dennisvink/python-age) — [PyPI python-age](https://pypi.org/project/python-age/)
- Wheel `python_age-0.1.0-py3-none-any.whl` installs top-level module name `age` (same import name as jojonas’ package) — inspected wheel `top_level.txt` / contents; [PyPI python-age](https://pypi.org/project/python-age/)
- PyPI package `age-rt` v0.2.2 (Johannes Dröge / parsimonit): “minimalistic Python implementation of age-encryption.org including an unofficial real-time variant”; Python >=3.10; MIT; depends on `cryptography>=41.0.0`; repo [parsimonit/python-age-rt](https://github.com/parsimonit/python-age-rt) — [PyPI age-rt](https://pypi.org/project/age-rt/)
- Wheel `age_rt-0.2.2-py3-none-any.whl` ships single module `age_rt.py` (import `age_rt`) — inspected wheel; [PyPI age-rt](https://pypi.org/project/age-rt/)
- PyPI package `age` v0.5.1 is jojonas’ **pyage** (“Actually good encryption. In Python.”); Python `>=3.6,<4`; last release 2023-05-06; docs at [pyage.readthedocs.io](https://pyage.readthedocs.io/); repo [jojonas/pyage](https://github.com/jojonas/pyage) — [PyPI age](https://pypi.org/project/age/)
- PyPI package named `pyage` is unrelated: “Python Agent-based evolution” v1.2.12 — PyPI name collision check 2026-10-25
- PyPI `pyrage` v1.4.0: Python bindings for Rust `rage` / age; Python >=3.10; ships abi3 wheels for manylinux x86_64/aarch64, macOS universal2, win_amd64 plus sdist — [PyPI pyrage](https://pypi.org/project/pyrage/); [woodruffw/pyrage](https://github.com/woodruffw/pyrage)
- PyPI `ssage` v1.5.2: wrapper around default backend `age` (jojonas), optional `pyrage`, or native `age`/`age-keygen` binaries; Python >=3.10 — [PyPI ssage](https://pypi.org/project/ssage/); [esoadamo/ssage](https://github.com/esoadamo/ssage)
- PyPI `rage` is Windows registry manipulation, not age encryption — name check 2026-10-25
- GitHub user `dfrankland` has no public Python age-format repository; top repos are unrelated (ampreact, envoluntary, bluster, etc.) — [dfrankland profile](https://github.com/dfrankland)
- `saltstack-age` uses `pyrage` for Salt pillar secrets (not a general streaming library) — [PyPI saltstack-age](https://pypi.org/project/saltstack-age/)

### Inferences
- For a greenfield Python 3.11+ dependency choice aimed at stock age v1 + passphrase streaming, the shortlist is effectively `python-age`, `age-rt` (AgeEncoder path only), or staying with/waiting on `pyrage`.
- `ssage` does not add a new crypto implementation; it layers UX on jojonas `age` / pyrage / CLI.
- Package naming is hazardous: PyPI `age` ≠ PyPI `python-age` ≠ import `age` uniqueness; PyPI `pyage` ≠ jojonas project nicknamed pyage.

### Gaps
- No comprehensive PyPI full-text search API was available in this session; enumeration used known names plus targeted searches, so an obscure niche package could still exist.
- Download-count absolute rankings beyond the per-project PyPI “Last month” figures were not independently audited.

## Which support passphrase (scrypt recipient) vs only X25519?

### Takeaway
Passphrase/scrypt is available in `python-age`, `age-rt` (passphrase-only), jojonas `age`/pyage, and `pyrage`. `age-rt` has no X25519/SSH yet. Only jojonas pyage and pyrage document SSH recipients among the surveyed libraries.

### Cited Findings
- Stock age scrypt stanza: `-> scrypt <base64-16-byte-salt> <logN>` with wrap key `scrypt(N=2^logN, r=8, p=1, dkLen=32, S="age-encryption.org/v1/scrypt"||salt, P=passphrase)`; scrypt must be the only stanza — [C2SP age v1.1.0](https://c2sp.org/age@v1.1.0); [C2SP age.md](https://github.com/C2SP/C2SP/blob/main/age.md)
- `python-age` documents support for X25519 recipients (`age1...`) and scrypt passphrase (`-p`); explicitly does **not** implement SSH keys, plugins, armor, or post-quantum hybrid keys — [PyPI python-age](https://pypi.org/project/python-age/); [dennisvink/python-age](https://github.com/dennisvink/python-age)
- `python-age` exposes `ScryptRecipient`, `ScryptIdentity`, `X25519Recipient`, `X25519Identity` in its programmatic API — [PyPI python-age](https://pypi.org/project/python-age/)
- `age-rt` states: “**It currently only supports the passphrase mode**”; scrypt parameters documented as N=2^18, r=8, p=1 (age v1 standard) — [PyPI age-rt](https://pypi.org/project/age-rt/); [parsimonit/python-age-rt](https://github.com/parsimonit/python-age-rt)
- jojonas pyage includes `age.algorithms.scrypt`, `age.recipients.scrypt`, `age.keys.password.PasswordKey`, plus X25519 and SSH ed25519/RSA modules; CLI `-p` adds a password recipient — [pyage API docs](https://pyage.readthedocs.io/en/latest/api/age.html)
- `pyrage` documents `passphrase.encrypt` / `passphrase.decrypt`, plus `x25519` and `ssh` recipient/identity types — [PyPI pyrage](https://pypi.org/project/pyrage/); [woodruffw/pyrage README](https://github.com/woodruffw/pyrage/blob/main/README.md)
- `ssage` examples focus on private/public key string encrypt/decrypt; backends include Python age, native binaries, and pyrage — [PyPI ssage](https://pypi.org/project/ssage/)

### Inferences
- If the product needs both passphrase dumps and SSH/X25519 recipient mode from one library, `python-age` covers X25519+passphrase but not SSH; `pyrage` covers all three (with passphrase streaming still incomplete); `age-rt` cannot cover recipient mode today.
- Spec-level scrypt uniqueness (cannot mix with other recipients) is already reflected in `python-age` CLI docs (“passphrase recipients cannot be mixed with `-r` or `-R`”).

### Gaps
- Exact `ssage` passphrase API surface was not fully exercised from source in this pass (docs emphasize key-based examples).
- Independent cryptographic review status is “none claimed” for `python-age` and explicitly “NOT INDEPENDENTLY REVIEWED” for `age-rt`; neither was audited here.

## Which support streaming IO (file-like / incremental) vs bytes-only?

### Takeaway
True chunked streaming for stock age v1 passphrase is implemented in `python-age` (`encrypt_file`/`decrypt_file`) and `age-rt` (`AgeEncoder`/`AgeDecoder` + iterators). jojonas pyage’s `Encryptor`/`Decryptor` look file-like but buffer the entire payload. `pyrage` has recipient `encrypt_io`/`decrypt_io` but passphrase remains bytes-only as of v1.4.0 (open issue #172).

### Cited Findings
- `python-age` documents file-like streaming: `encrypt_file(src, dst, recipients)` / `decrypt_file(src, dst, identities)` — [PyPI python-age](https://pypi.org/project/python-age/)
- Inspected `python-age` source: `CHUNK_SIZE = 64 * 1024`; `encrypt_stream` reads ~64 KiB+1 incrementally and writes AEAD chunks; `decrypt_stream` reads encrypted chunks incrementally — wheel `age.py` in [python-age 0.1.0](https://pypi.org/project/python-age/)
- `age-rt` provides push-based `AgeEncoder`/`AgeDecoder` for **standard age v1**, plus `AgeRTEncoder`/`AgeRTDecoder` for the unofficial variable-length format; also `encode_file`/`decode_file`, sync/async iterators — [PyPI age-rt](https://pypi.org/project/age-rt/)
- `age-rt` `AgeEncoder` requires non-final plaintext chunks to be exactly `chunk_size` (default 65536); short chunk = final — [PyPI age-rt](https://pypi.org/project/age-rt/)
- jojonas `age.file.Encryptor.write` appends to `_plaintext_buffer`; encryption happens only in `close()` via `stream_encrypt(stream_key, self._plaintext_buffer)`; `Decryptor._decrypt_body` does `ciphertext = self._stream.read()` then decrypts all at once into `BytesIO` — inspected [age 0.5.1](https://pypi.org/project/age/) wheel `age/file.py`; also [pyage API docs](https://pyage.readthedocs.io/en/latest/api/age.html)
- jojonas `age.stream.stream_encrypt` / `stream_decrypt` take full `bytes` and return full `bytes` — inspected `age/stream.py` in [age 0.5.1](https://pypi.org/project/age/)
- `pyrage` public README still documents only bytes APIs for encrypt/decrypt and passphrase — [woodruffw/pyrage README](https://raw.githubusercontent.com/woodruffw/pyrage/main/README.md)
- `pyrage` v1.4.0 `src/lib.rs` implements top-level `encrypt_io(reader, writer, recipients, armored=false)` and `decrypt_io(reader, writer, identities)` using `std::io::copy` over rage’s streaming Encryptor/Decryptor — [pyrage v1.4.0 lib.rs](https://raw.githubusercontent.com/woodruffw/pyrage/v1.4.0/src/lib.rs)
- `pyrage` `passphrase` module in v1.4.0 only wraps one-shot `encrypt`/`decrypt` that collect into `Vec<u8>` — [pyrage v1.4.0 passphrase.rs](https://raw.githubusercontent.com/woodruffw/pyrage/v1.4.0/src/passphrase.rs)
- Open issue: “Streaming passphrase encrypt_io / decrypt_io” (#172, opened 2026-10-21 by ravensorb); notes recipient streaming already exists; passphrase binding gap; PR sketch #171 closed without merge — [pyrage#172](https://github.com/woodruffw/pyrage/issues/172)
- Related open issue #168: configure `encrypt_io`/`decrypt_io` buffer size as multiple of age’s 64 KiB block — [pyrage#168](https://github.com/woodruffw/pyrage/issues/168)
- Third-party usage (kassiber) documents preferring `age`/`rage` binaries for streaming and treating `pyrage` passphrase as in-memory fallback (`payload = source.read()` then `pyrage.passphrase.encrypt`) — [kassiber age_cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/age_cli.py)
- `ssage` examples encrypt/decrypt whole strings in memory — [PyPI ssage](https://pypi.org/project/ssage/)

### Inferences
- For multi-GB passphrase dumps without buffering, `python-age` and `age-rt` (`AgeEncoder`/`AgeDecoder`) are the only surveyed pure-Python libraries with genuine incremental STREAM chunking.
- jojonas pyage must be classified as **not streaming** despite a file-like API surface.
- `pyrage` can already stream **recipient** mode via `encrypt_io`/`decrypt_io`; passphrase streaming depends on upstream accepting #172 (or using a binary / alternate library).

### Gaps
- Memory ceiling of `python-age` / `age-rt` during scrypt KDF (~256 MiB at work factor 18) is separate from payload streaming and was not benchmarked here.
- Whether `age-rt` `encode_file` accepts a file-like plaintext source (vs iterable of chunks only) was documented as taking `chunks: Iterable[bytes]` written to a file-like destination — callers must chunk a large file themselves.

## Can output be decrypted by stock `age -d` / FiloSottile age?

### Takeaway
Authors of `python-age` and `age-rt` (AgeEncoder path) claim Go/`age` interoperability for standard age v1 passphrase (and X25519 for python-age). `age-rt`’s own `AgeRTEncoder` format is **not** stock-compatible. jojonas pyage has an open report of failing to decrypt stock age passphrase files. `pyrage`/rage is designed for stock compatibility.

### Cited Findings
- `python-age`: “Compatible with the Go `age` tool for X25519 and scrypt recipients.” — [PyPI python-age](https://pypi.org/project/python-age/)
- `age-rt`: “Compatibility with the official Go age implementation (for the age part)”; wire format for age v1 uses fixed-size chunks matching stock STREAM; age-rt v0.2 uses length-prefixed chunks — [PyPI age-rt](https://pypi.org/project/age-rt/)
- `age-rt` tests distinguish formats: `AgeRTDecoder` must reject age v1 wire; `AgeDecoder` must reject age-rt wire; custom non-65536 chunk sizes rewrite the identifier with `?chunk=` / `?maxchunk=` and are documented as non-interoperable — [test_formats.py](https://raw.githubusercontent.com/parsimonit/python-age-rt/main/tests/test_formats.py); [PyPI age-rt](https://pypi.org/project/age-rt/)
- `age-rt` test README lists format interoperability as age-rt vs age v1 **within the package**; “Not Covered” does not list external `age` binary cross-tests; large payloads tested “up to 5 MB” — [age-rt tests/README.md](https://raw.githubusercontent.com/parsimonit/python-age-rt/main/tests/README.md)
- jojonas pyage issue #14 (open, 2024-11-25): passphrase file generated by stock age decrypts with `age`/`rage` but `pyage decrypt` crashes before prompting — [jojonas/pyage#14](https://github.com/jojonas/pyage/issues/14)
- jojonas pyage README: “⚠️ pyage is not intended to be a secure age implementation!” — [PyPI age](https://pypi.org/project/age/)
- `pyrage` binds rage (Rust age); maintainer blog presents it as interoperable age encryption for Python — [yossarian.net pyrage article](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage); [woodruffw/pyrage](https://github.com/woodruffw/pyrage)
- C2SP age STREAM uses 64 KiB plaintext chunks + ChaCha20-Poly1305; matching chunk size is required for stock interoperability — [C2SP age v1.1.0](https://c2sp.org/age@v1.1.0)

### Inferences
- Safe recommendation for stock `age -d` recovery: prefer `python-age` or `age-rt.AgeEncoder` (default chunk 65536) or `pyrage`/rage; never ship `AgeRTEncoder` ciphertext if stock decrypt is required.
- jojonas pyage should not be relied on for stock interoperability given #14 and the project’s own security disclaimer.

### Gaps
- This research did **not** run live round-trips (`python-age`/`age-rt` encrypt → `age -d`, or reverse) on 2026-10-25; interoperability for those two rests on author claims plus format alignment, not freshly verified binary tests here.
- No published third-party audit comparing ciphertext byte-for-byte against FiloSottile age was found for `python-age` or `age-rt`.

## Activity, stars, last release, known bugs, Python version support

### Takeaway
`pyrage` is the only mature, actively maintained, widely downloaded option (but passphrase streaming incomplete). `age-rt` and `python-age` are young/low-visibility (0 stars). jojonas pyage is effectively abandoned since mid-2023 with known compatibility and Python 3.12 packaging bugs. All shortlisted packages support Python 3.11+.

### Cited Findings

| Package | PyPI / repo | Stars | Last release | Last push (GitHub API) | License | Python | Packaging |
|--------|-------------|-------|--------------|------------------------|---------|--------|-----------|
| pyrage | [pypi.org/project/pyrage](https://pypi.org/project/pyrage/) / [woodruffw/pyrage](https://github.com/woodruffw/pyrage) | 92 | 1.4.0 on 2026-08-23 | 2026-10-19 | MIT | >=3.10 | Native abi3 wheels + sdist |
| age-rt | [pypi.org/project/age-rt](https://pypi.org/project/age-rt/) / [parsimonit/python-age-rt](https://github.com/parsimonit/python-age-rt) | 0 | 0.2.2 on 2026-05-28 | 2026-05-28 | MIT | >=3.10 | Pure-Python wheel + sdist |
| python-age | [pypi.org/project/python-age](https://pypi.org/project/python-age/) / [dennisvink/python-age](https://github.com/dennisvink/python-age) | 0 | 0.1.0 on 2026-01-09 | 2026-01-09 | BSD-3-Clause | >=3.9 | Pure-Python wheel + sdist |
| age (pyage) | [pypi.org/project/age](https://pypi.org/project/age/) / [jojonas/pyage](https://github.com/jojonas/pyage) | 34 | 0.5.1 on 2023-05-06 | commits last 2023-05-06; `pushed_at` 2023-11-13 | MIT | >=3.6,<4 | Pure-Python wheel + sdist |
| ssage | [pypi.org/project/ssage](https://pypi.org/project/ssage/) / [esoadamo/ssage](https://github.com/esoadamo/ssage) | 1 | 1.5.2 on 2026-10-01 | 2026-10-01 | MIT | >=3.10 | sdist (depends on `age`) |

GitHub metadata from API 2026-10-25: [woodruffw/pyrage](https://api.github.com/repos/woodruffw/pyrage), [parsimonit/python-age-rt](https://api.github.com/repos/parsimonit/python-age-rt), [dennisvink/python-age](https://api.github.com/repos/dennisvink/python-age), [jojonas/pyage](https://api.github.com/repos/jojonas/pyage), [esoadamo/ssage](https://api.github.com/repos/esoadamo/ssage).

- PyPI download stats (approx., project pages): pyrage ~527k last month; jojonas `age` ~11k; `python-age` ~832; `ssage` ~993; `age-rt` ~45 — respective PyPI project pages
- `age-rt` v0.2.2 release note/tag message: “Fix broken iterator wrapper with standard age decryption.” — [python-age-rt tags](https://github.com/parsimonit/python-age-rt/tags)
- `age-rt` security disclaimer: “THIS PACKAGE IMPLEMENTATION IS NOT INDEPENDENTLY REVIEWED!” — [PyPI age-rt](https://pypi.org/project/age-rt/)
- jojonas open issues include #14 stock-age decrypt failure; #15/#16 Python 3.12 install breakage via old versioneer/`SafeConfigParser`; #6 scrypt recipient parser accepts non-canonical integer encodings — [jojonas/pyage issues](https://github.com/jojonas/pyage/issues)
- `python-age`: single initial feature commit + README pip note on 2026-01-09; 0 open issues; 0 stars — [dennisvink/python-age](https://github.com/dennisvink/python-age)
- `pyrage` open issues include #172 passphrase streaming and #168 IO buffer sizing; 5 open issues total — [woodruffw/pyrage](https://github.com/woodruffw/pyrage)

### Inferences
- **Dead/abandoned (call out clearly):** jojonas/pyage (`pip install age`) — no meaningful commits since 2023-05-06, security disclaimer, open stock-interop and 3.12 packaging bugs; treat as legacy/experimental only.
- **Young / low maturity:** `python-age` (one release, no community signal) and `age-rt` (four releases over ~8 days in May 2026, then quiet; 0 stars; unaudited).
- **Actively maintained:** `pyrage` (releases through 2026-08, pushes into Oct 2026, high download volume).
- All of `python-age`, `age-rt`, and `pyrage` meet Python 3.11+ requirements.

### Gaps
- Exact CVE/advisory search for these packages was not performed.
- Star counts for small repos can understate private use; download stats are a better activity proxy for pyrage vs newcomers.

## Can they coexist with or replace pyrage for recipient mode too?

### Takeaway
`age-rt` cannot replace pyrage for recipient/SSH mode (passphrase-only). `python-age` can cover X25519 + passphrase streaming and could coexist with pyrage on different import paths only if the jojonas `age` package is absent — but it conflicts with PyPI `age` on the `age` module name. Best coexistence pattern today: keep `pyrage` for recipient (`encrypt_io`) + SSH, and add `age-rt` or `python-age` only for passphrase streaming (or wait for pyrage #172).

### Cited Findings
- `age-rt` limitation: “Passphrase mode only (no public key support yet)” — [PyPI age-rt](https://pypi.org/project/age-rt/)
- `python-age` supports X25519 + scrypt; no SSH/plugins/armor — [PyPI python-age](https://pypi.org/project/python-age/)
- Import conflict: both `python-age` and jojonas `age` install top-level module `age` — inspected wheels 2026-10-25
- `age_rt` import name does not collide with `pyrage` — inspected `age_rt` wheel
- `pyrage` already streams recipient mode via `encrypt_io`/`decrypt_io` and supports SSH + X25519 — [pyrage v1.4.0 lib.rs](https://raw.githubusercontent.com/woodruffw/pyrage/v1.4.0/src/lib.rs); [PyPI pyrage](https://pypi.org/project/pyrage/)
- `ssage` can select backends (`age` / native / `pyrage`) but string-oriented API and default jojonas backend make it a poor replacement for streaming dumps — [PyPI ssage](https://pypi.org/project/ssage/)

### Inferences
- **Replace pyrage entirely:** only plausible with `python-age` if SSH and armor are out of scope and the team accepts a brand-new 0.1.0 dependency; still need stock-`age` cross-tests.
- **Coexist:** `pyrage` (recipient streaming + SSH) + `age-rt.AgeEncoder` (passphrase streaming) avoids import clashes; `pyrage` + `python-age` also works if `pip install age` (jojonas) is never pulled in transitively (watch `ssage` and similar).
- Waiting on [pyrage#172](https://github.com/woodruffw/pyrage/issues/172) would keep a single mature dependency for both modes if maintainers accept passphrase `encrypt_io`/`decrypt_io`.

### Gaps
- No decision recommendation is finalized here beyond capability mapping; product risk tolerance for unaudited pure-Python crypto vs waiting on pyrage was out of scope.
- Transitive dependency graph of this repo (`l3io-wordpress-database`) was not inspected (research-only constraint; no code changes).
