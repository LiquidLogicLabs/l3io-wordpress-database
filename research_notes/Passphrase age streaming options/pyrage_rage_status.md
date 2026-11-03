# pyrage / rage status: streaming passphrase encryption

Research date: **2026-10-25**. Scope: stock pyrage/rage APIs, maintainer position on woodruffw/pyrage#172 and closed PR #171, and whether waiting on upstream is realistic for multi-GB passphrase streams.

## What exact APIs does pyrage 1.4+ expose for passphrase vs recipients?

### Takeaway
pyrage **1.4.0** (current PyPI as of 2026-10-25; Cargo.toml also `1.4.0`) exposes **streaming recipient** APIs (`encrypt_io` / `decrypt_io`, plus path-based `*_file`) but **only one-shot bytes** APIs under `pyrage.passphrase` — no `passphrase.encrypt_io` / `decrypt_io` on main or PyPI.

### Cited Findings
- Latest PyPI version is **1.4.0** (requires Python `>=3.10`); published ~2026-08-23. — [PyPI pyrage](https://pypi.org/project/pyrage/); [deps.dev attestation](https://deps.dev/pypi/pyrage)
- Package version in source: `version = "1.4.0"`; depends on `age = { version = "0.12.1", features = ["armor", "plugin", "ssh"] }` and `pyo3-file = "0.17.0"`. — [Cargo.toml (main)](https://raw.githubusercontent.com/woodruffw/pyrage/main/Cargo.toml)
- **Recipient (top-level) APIs** exported from `src/lib.rs` / stubs:
  - `encrypt(plaintext: bytes, recipients, armored=False) -> bytes`
  - `encrypt_file(infile: str, outfile: str, recipients, armored=False) -> None`
  - `encrypt_io(reader, writer, recipients, armored=False) -> None` (file-like via `PyFileLikeObject`; `std::io::copy` through rage `Encryptor::with_recipients` + `wrap_output`)
  - `decrypt(ciphertext: bytes, identities) -> bytes`
  - `decrypt_file(infile, outfile, identities) -> None`
  - `decrypt_io(reader, writer, identities) -> None`
  — [src/lib.rs (main)](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/lib.rs); [__init__.pyi](https://raw.githubusercontent.com/woodruffw/pyrage/main/pyrage-stubs/pyrage/__init__.pyi)
- **Passphrase APIs** (`src/passphrase.rs` / stubs) — only:
  - `passphrase.encrypt(plaintext: bytes, passphrase: str, armored=False) -> bytes`
  - `passphrase.decrypt(ciphertext: bytes, passphrase: str) -> bytes` (Rust signature has no `armored` flag; decryption uses `ArmoredReader` and auto-detects)
  - Module registers **only** those two wrapped functions; no `*_io` / `*_file`.
  — [passphrase.rs (main)](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs); [passphrase.pyi](https://raw.githubusercontent.com/woodruffw/pyrage/main/pyrage-stubs/pyrage/passphrase.pyi)
- README documents recipient one-shot + passphrase one-shot only; it does **not** document `encrypt_io` / `decrypt_io` / `*_file` despite them existing in the library. — [README.md (main)](https://raw.githubusercontent.com/woodruffw/pyrage/main/README.md)
- Stub quirk: `__init__.pyi` types `encrypt_io(...) -> bytes` while Rust returns `PyResult<()>`; `passphrase.pyi` types `decrypt(..., armored=False)` but Rust `decrypt` has no `armored` parameter. — [__init__.pyi](https://raw.githubusercontent.com/woodruffw/pyrage/main/pyrage-stubs/pyrage/__init__.pyi); [passphrase.pyi](https://raw.githubusercontent.com/woodruffw/pyrage/main/pyrage-stubs/pyrage/passphrase.pyi); [passphrase.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs)
- Recipient streaming landed via PR #77 (merged 2024-09-26, released **v1.2.0**), fixing issue #36. — [PR #77](https://github.com/woodruffw/pyrage/pull/77); [issue #36](https://github.com/woodruffw/pyrage/issues/36)
- Passphrase path buffers full plaintext/ciphertext into `Vec` / `PyBytes` (same pattern as the 2022 design write-up). — [passphrase.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs); [woodruffw blog 2022-07-25](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage)

### Inferences
- For this package’s constraints: **recipient multi-GB streaming is already available in stock pyrage ≥1.2**; **passphrase multi-GB streaming is not** without buffering the whole payload in Python/`bytes`.
- The binding gap is asymmetric by design of the exposed surface, not because passphrase crypto is absent — passphrase encrypt already calls the same streaming Rust writer API, then collects into a `Vec`.

### Gaps
- Exact PyPI upload changelog / release notes text for 1.4.0 (what changed vs 1.3.0) was not retrieved beyond version metadata and README copy; armor landed in 1.3.0 era via #116 / issue #45.

## Does the underlying rage / age crate already stream passphrase encrypt/decrypt?

### Takeaway
Yes. The Rust `age` crate (used by pyrage as dependency `age` 0.12.1 from the str4d/rage workspace) already provides **streaming** passphrase encryption via `Encryptor::with_user_passphrase` + `wrap_output` → `StreamWriter`, and streaming decrypt via `Decryptor` + `scrypt::Identity`. pyrage’s passphrase module only chooses to read/write full buffers around those APIs.

### Cited Findings
- `Encryptor::with_user_passphrase(passphrase: SecretString) -> Self` builds an encryptor for passphrase (scrypt recipient) files; docs say use only with human-provided passphrases. — [docs.rs age::Encryptor 0.12.1](https://docs.rs/age/latest/age/struct.Encryptor.html)
- `wrap_output` returns `StreamWriter<W>`; callers must `finish()` or the file is truncated and will not decrypt. — [docs.rs age::Encryptor](https://docs.rs/age/latest/age/struct.Encryptor.html); [StreamWriter::finish](https://docs.rs/age/latest/age/stream/struct.StreamWriter.html)
- Implementation: `with_user_passphrase` delegates to `with_recipients(iter::once(&scrypt::Recipient::new(passphrase)))`. — [protocol.rs source on docs.rs](https://docs.rs/age/latest/src/age/protocol.rs.html)
- pyrage’s one-shot passphrase encrypt already uses that stack (`Encryptor::with_user_passphrase` → `wrap_output` → `write_all(plaintext)` → `finish`), writing into an in-memory `Vec`. Decrypt uses `Decryptor::new_buffered(ArmoredReader::new(ciphertext))` then `decrypt(iter::once(&scrypt::Identity::new(...)))` and `read_to_end`. — [passphrase.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs)
- age format: “seekable streaming encryption”; payload is STREAM (ChaCha20-Poly1305 chunks). Passphrase mode is the **scrypt** recipient stanza (`-> scrypt ...`), not a separate wire format. — [age-encryption.org/v1](https://age-encryption.org/v1); passphrase ciphertext examples in [issue #45 discussion](https://github.com/woodruffw/pyrage/issues/45)
- Stock `age` CLI: “Files can be encrypted with a passphrase by using `-p/--passphrase`”; passphrase files auto-detected at decrypt. — [FiloSottile/age README](https://github.com/FiloSottile/age)

### Inferences
- Closing the gap for stock `age -d`-compatible scrypt ciphertext with bounded memory is a **Python binding / API-surface** problem, not a missing capability in rage/`age` 0.12.
- A mirrored `passphrase.encrypt_io` would be mechanically similar to existing recipient `encrypt_io` (swap `with_recipients` for `with_user_passphrase` / `scrypt::Identity`) — which is what closed PR #171 attempted.

### Gaps
- Did not re-audit rage CLI (`rage -p`) streaming behavior beyond the library API; library streaming is sufficient for the binding question.
- Exact scrypt work-factor / memory cost at encrypt time (fixed scrypt cost vs streaming payload) not quantified here; ADR/handoff notes in this repo already treat scrypt as a large fixed cost separate from peak RSS of the payload stream.

## What did woodruffw say on #172 / #171, and is the issue still open with no commitment?

### Takeaway
**#172 is still open** (as of 2026-10-25) with **no maintainer commitment** to add passphrase streaming. woodruffw closed and locked #171 (as spam), then on #172 said he closed it for LLM authorship and, at a high level, **does not want to add more streaming APIs** because they are hard to get right — while still asking to understand the real problem. After the requester’s human clarification (multi-GB WordPress DB backups / memory), there has been **no further maintainer reply** (last activity 2026-10-21).

### Cited Findings
- Issue #172 “Streaming passphrase encrypt_io / decrypt_io”: **state=open**, created 2026-10-21 by ravensorb, proposes `pyrage.passphrase.encrypt_io` / `decrypt_io` mirroring recipient IO; references closed #171. — [issue #172](https://github.com/woodruffw/pyrage/issues/172); [API issue object](https://api.github.com/repos/woodruffw/pyrage/issues/172)
- woodruffw (2026-10-21T13:24:34Z): “I closed #171 because it wasn't written in your own words, and this isn't either. Please explain the problem yourself rather than having your LLM explain it. **(At a high level, I don't want to add more streaming APIs. They're hard to get right. But I'd like to understand what problem you're actually trying to solve.)**” — [comment](https://github.com/woodruffw/pyrage/issues/172#issuecomment-6317197865)
- ravensorb (2026-10-21T16:30:50Z): clarified large (>1GB) WordPress DB backups and need to reduce memory for passphrase byte streams; open to other suggestions. — [comment](https://github.com/woodruffw/pyrage/issues/172#issuecomment-6321072610)
- Issue `updated_at` is 2026-10-21T16:30:50Z (that reply); only **2 comments**; `closed_at: null`. No labels, assignees, or milestone. — [API issue object](https://api.github.com/repos/woodruffw/pyrage/issues/172)
- PR #171 “Add passphrase.encrypt_io and decrypt_io”: **closed**, **not merged**, **locked** with `active_lock_reason: "spam"`; created 2026-10-21T01:53:21Z, closed 2026-10-21T05:28:51Z; body marked “Made with Cursor”; +262/−3. — [PR #171](https://github.com/woodruffw/pyrage/pull/171); [API PR object](https://api.github.com/repos/woodruffw/pyrage/pulls/171)
- Same LLM-authorship sensitivity appears on nearby issue #168 (buffer sizing for existing `encrypt_io`): woodruffw asked not to use LLMs on the repo and preferred non-configurable internal buffer bump over new public streaming knobs. — [issue #168](https://github.com/woodruffw/pyrage/issues/168)

### Inferences
- Closure of #171 was primarily about **process / authorship / spam lock**, not a technical review rejecting the patch’s approach.
- The substantive signal on scope is the parenthetical: **reluctance to grow the streaming API surface**, not “rage can’t do it.”
- “No commitment” is accurate: open issue + unanswered clarification + explicit preference against more streaming APIs.

### Gaps
- Whether woodruffw will reply after 2026-10-21 is unknowable; as of research day there is silence for ~4 days.
- Full #171 review discussion is empty (`comments: 0`); locked PR may hide or prevent further thread — API shows zero issue comments on the PR.

## Are there related issues/PRs or prior refusals of streaming APIs?

### Takeaway
Recipient streaming was **initially resisted** (prefer paths/fds/memfd over file-like objects) then **accepted and shipped** (#36 → #77 → v1.2.0). There is **no prior closed refusal specifically of passphrase streaming** before #171/#172. Recent maintainer posture (Oct 2026) is cooler toward *additional* streaming API surface and toward LLM-authored proposals (#168, #172).

### Cited Findings
- Issue #36 (2023-07): request for streaming decrypt from Python file-like objects. woodruffw first preferred avoiding fileobj APIs (interpreter overhead), suggested memfd/FIFO/raw fds; later acknowledged fileobj was “probably for the best” and welcomed a PR based on earlier #32 work. — [issue #36](https://github.com/woodruffw/pyrage/issues/36)
- PR #77 merged 2024-09-26: re-added file-handle/`PyFileLikeObject` streaming (`encrypt_io` / `decrypt_io`); woodruffw released **v1.2.0** same day. — [PR #77](https://github.com/woodruffw/pyrage/pull/77)
- Issue #168 (opened 2026-10-10, still open): proposes configurable `buffer_blocks` on `encrypt_io`/`decrypt_io`. woodruffw pushed back on configurability and LLM tone; suggested possibly bumping internal buffer to 128 KiB to match `io.DEFAULT_BUFFER_SIZE` without public API change. Requester agreed to drop the parameter. — [issue #168](https://github.com/woodruffw/pyrage/issues/168)
- Issue #172 references #36 (recipient streaming), #3 (passphrase one-shot), and #168 (orthogonal buffer sizing). — [issue #172](https://github.com/woodruffw/pyrage/issues/172)
- Maintainer’s original design blog (2022): “As small an API as possible”; passphrase called out as special-cased because it doesn’t fit identity/recipient cleanly; only bytes in/out for passphrase. — [blog.yossarian.net 2022-07-25](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage)
- Third-party pattern: some projects prefer `age`/`rage` CLI for streaming and fall back to in-memory pyrage for passphrase (and document that binary passphrase via subprocess is awkward because `--passphrase` wants a TTY / secret channel). — [kassiber age_cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/age_cli.py) (secondary example; not upstream)

### Inferences
- Historical arc: **streaming was hard-won for recipients**, not enthusiastically expanded. Extending the same pattern to passphrase is a small code delta but a **new public API** the maintainer now says he does not want “more of.”
- #168 shows preference for **internal** tweaks over new knobs — consistent with reluctance on #172, though #168 is about buffer size on existing IO, not passphrase.

### Gaps
- Issue #3 (passphrase one-shot origin) was not fetched in full; cited only via #172’s “prior art” list.
- No search hit for an older dedicated “passphrase streaming” request that was closed as won’t-fix before 2026-10.

## What would “wait for upstream” realistically mean given their stance?

### Takeaway
Waiting for stock PyPI pyrage to grow `passphrase.encrypt_io` / `decrypt_io` is **high-risk / low-predictability**: the maintainer’s stated preference is against more streaming APIs; #172 is open but unanswered after the problem statement; #171 was locked as spam. A realistic “upstream” path is months-to-indefinite unless a **human-authored**, narrowly scoped follow-up changes woodruffw’s mind — not a near-term floor to pin on.

### Cited Findings
- Explicit stance: “I don't want to add more streaming APIs. They're hard to get right.” — [woodruffw on #172](https://github.com/woodruffw/pyrage/issues/172#issuecomment-6317197865)
- Process gate: LLM-authored PR/issue text is actively demotivating and was enough to close/lock #171 and challenge #172/#168. — [#172](https://github.com/woodruffw/pyrage/issues/172); [#168](https://github.com/woodruffw/pyrage/issues/168); [PR #171 locked spam](https://api.github.com/repos/woodruffw/pyrage/pulls/171)
- Contrast: when woodruffw *did* accept streaming (#77), release followed within days of merge (v1.2.0). The bottleneck is **acceptance**, not packaging latency after merge. — [PR #77](https://github.com/woodruffw/pyrage/pull/77)
- Technical feasibility is not the blocker: rage already streams; recipient `encrypt_io` is the template. — [passphrase.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs); [lib.rs encrypt_io](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/lib.rs); [age::Encryptor](https://docs.rs/age/latest/age/struct.Encryptor.html)
- Stock age-compatible passphrase ciphertext = scrypt sole recipient in the v1 format; `age -d` recovers with passphrase. That format does not require a new pyrage API — only a streaming binder or an alternative producer (CLI / other library). — [age-encryption.org/v1](https://age-encryption.org/v1); [FiloSottile/age](https://github.com/FiloSottile/age)

### Inferences
- **“Wait for upstream”** in practice means: keep watching #172; any new PR should wait for an explicit maintainer “yes, in scope” and must be clearly human-written; do **not** treat merge+PyPI as a sprint dependency.
- Even a perfect technical PR may be declined on product grounds (“no more streaming APIs”), independent of WordPress dump size.
- Realistic alternatives if stock pyrage remains blocked (out of scope to choose here, but implied by stance):
  1. **Git-pin / fork** of a `passphrase.encrypt_io` patch until/unless upstream merges (interim approach already discussed in this repo’s handoff notes).
  2. **Recipient-mode streaming** for large payloads (already in stock pyrage); passphrase only on small identity files — diverges from “operator decrypts with passphrase alone via `age -d`.”
  3. **External `age`/`rage` CLI** for passphrase streams — conflicts with “passphrase never on argv” unless a safe secret channel (TTY/`--passphrase` behavior) is solved; other projects report this as painful.
  4. **Non-stock format** — violates the stock age / scrypt requirement.

### Gaps
- No public roadmap or milestone in pyrage tying passphrase IO to a release.
- No second maintainer or stated succession plan found; throughput depends on woodruffw alone.
- Whether offering to maintain tests/docs or narrowing the API (e.g. path-only `passphrase.encrypt_file` without file-like objects) would change the “no more streaming APIs” stance is **untested** — not answered in #172.
)
