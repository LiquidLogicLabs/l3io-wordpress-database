# Fork / vendor / binding options for streaming passphrase age IO

Research date: 2026-10-25. Scope: ownership strategies when upstream `pyrage` will not ship `passphrase.encrypt_io` / `decrypt_io`. Project constraints from ADR-0003 and plan-4: no VCS deps in published metadata (`uv build --no-sources`); Gitea registry is temporary staging; this package must not publish secrets; recipient streaming already exists on stock `pyrage`.

## License of pyrage and rage — can we fork and publish?

### Takeaway
Yes: `pyrage` is MIT and the underlying `age` crate is MIT OR Apache-2.0, so forking, modifying, redistributing, and publishing under a new distribution name are explicitly allowed if copyright notices are preserved.

### Cited Findings
- `pyrage` LICENSE is the MIT License (Copyright 2022 William Woodruff), granting rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell, subject to retaining the copyright notice. — [woodruffw/pyrage LICENSE](https://raw.githubusercontent.com/woodruffw/pyrage/main/LICENSE)
- GitHub marks the repository license as MIT; the README states the same. — [woodruffw/pyrage](https://github.com/woodruffw/pyrage/); [README Licensing](https://github.com/woodruffw/pyrage/blob/main/README.md)
- `Cargo.toml` declares `license = "MIT"` for the `pyrage` crate (version 1.4.0 as of main). — [Cargo.toml](https://raw.githubusercontent.com/woodruffw/pyrage/main/Cargo.toml)
- The Rust `age` library (what library consumers should use; `rage` is the CLI) is dual-licensed MIT OR Apache-2.0 on crates.io. — [crates.io/crates/age](https://crates.io/crates/age); [LICENSE-MIT](https://github.com/str4d/rage/blob/main/LICENSE-MIT)
- str4d’s rage README directs applications wanting a library to the `age` crate, not to a C ABI. — [str4d/rage](https://github.com/str4d/rage/)
- PyPI packaging docs treat forks as a common reason for a new distribution name while optionally keeping the same import name; distribution names on an index must be unique. — [Distribution vs import package](https://github.com/pypa/packaging.python.org/blob/main/source/discussions/distribution-package-vs-import-package.rst)
- Taking over the existing `pyrage` PyPI name against a reachable owner is not allowed; PyPI name transfer requires demonstrated abandonment and that a differently named fork is not an acceptable workaround. — [PyPI Name Retention](https://docs.pypi.org/project-management/name-retention/)

### Inferences
- Publishing a fork as e.g. `pyrage-passphrase-io` or `l3io-pyrage` on PyPI or Gitea is legally fine under MIT, provided the LICENSE notice is kept and the distribution name does not claim to be the upstream project.
- Keeping `import pyrage` in a renamed distribution would conflict with installing stock `pyrage` in the same environment; a dedicated thin crate with a distinct import (e.g. `l3io_age_passphrase`) avoids that clash.
- Trademark / social risk is separate from copyright: naming something `pyrage` on PyPI while woodruffw still maintains the real package would confuse users and invite dependency-confusion concerns.

### Gaps
- No public statement from woodruffw was retrieved explaining why PR #171 was closed beyond GitHub metadata (`active_lock_reason: "spam"`, `merged: false`); intent beyond “not merging” is not documented in issue comments (comment count was 0).

## How hard is the PR #171-style change to maintain on a fork?

### Takeaway
The code delta is small and mostly a mechanical mirror of existing recipient `encrypt_io` / `decrypt_io`; ongoing cost is rebasing onto upstream `pyrage` / `age` / PyO3 bumps, not re-deriving crypto logic.

### Cited Findings
- Upstream `src/passphrase.rs` today only exposes buffered `encrypt` / `decrypt` that write into a `Vec<u8>` / read to end; there is no IO API. — [passphrase.rs on main](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs)
- Recipient-mode streaming already exists in `src/lib.rs` as `encrypt_io` / `decrypt_io` using `PyFileLikeObject`, `BufReader`/`BufWriter`, `Encryptor::with_recipients` / `Decryptor::new_buffered`, `io::copy`, and armor wrappers. — [lib.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/lib.rs)
- The ravensorb fork branch `passphrase-encrypt-io` adds `encrypt_io` / `decrypt_io` in `passphrase.rs` that call `Encryptor::with_user_passphrase` and `scrypt::Identity::new`, reusing `from_pyobject` from `lib.rs` — the same pattern as recipient IO. — [ravensorb passphrase.rs](https://raw.githubusercontent.com/ravensorb/pyrage/passphrase-encrypt-io/src/passphrase.rs)
- PR #171 against woodruffw/pyrage: +262 / −3 across 5 files; state closed, not merged; locked with `active_lock_reason: "spam"`; created 2026-10-21 by ravensorb; head repo `ravensorb/pyrage`. — [PR #171 API](https://api.github.com/repos/woodruffw/pyrage/pulls/171); [PR HTML](https://github.com/woodruffw/pyrage/pull/171)
- Plan-4 acceptance criteria for the upstream PR were: multi-chunk round-trip, flat peak RSS, stock `age -d` interop, wrong passphrase vs truncate error split, leave one-shot APIs unchanged. — project plan `_bmad-output/planning-artifacts/plans/2026-10-20-plan-4-passphrase-stream.md` (local)
- `age::Encryptor::with_user_passphrase` is a documented public API that wraps scrypt-only encryption; streaming is via `wrap_output` + `StreamWriter::finish`. — [docs.rs Encryptor](https://docs.rs/age/latest/age/struct.Encryptor.html); [StreamWriter](https://docs.rs/age/latest/age/stream/struct.StreamWriter.html)
- Current `pyrage` depends on `age = { version = "0.12.1", features = ["armor", "plugin", "ssh"] }`, `pyo3` 0.29.2 with `abi3` / `abi3-py310`, and `pyo3-file` 0.17.0. — [Cargo.toml](https://raw.githubusercontent.com/woodruffw/pyrage/main/Cargo.toml)

### Inferences
- Maintaining a full `pyrage` fork means periodically merging upstream main (SSH/plugin/tag/tagpq/x25519 churn, PyO3 upgrades, age 0.x bumps) even though the passphrase-IO patch itself is ~tens of lines of logic plus tests/stubs.
- Making `from_pyobject` crate-visible (as the fork does) is a small structural coupling: if upstream changes that helper’s signature, the passphrase IO functions break in the same way recipient IO would.
- Divergence risk is highest when upstream refuses the API and later adds a different streaming passphrase shape; a fork that keeps the PR #171 names (`encrypt_io`/`decrypt_io`) stays aligned with l3io’s planned call sites.

### Gaps
- Exact contents of the other four files in the +262 PR (tests, stubs, `lib.rs` visibility of `from_pyobject`, docs) were not fully enumerated beyond `passphrase.rs`; line-level maintenance estimate for stubs/CI is approximate.
- No measurement of rebase frequency against historical `pyrage` release cadence was collected beyond the current 1.4.0 pin and Aug 2026 PyPI upload times.

## Publishing a fork under a different PyPI name vs private Gitea index

### Takeaway
A differently named public PyPI package is the only ownership path that fits a future public release of `l3io-wordpress-database` without VCS deps or private-index auth; a Gitea PyPI registry works for private/staging installs but conflicts with “Gitea is temporary staging” and with consumers who only talk to public PyPI.

### Cited Findings
- ADR-0003: published metadata pins `pyrage>=1.4,<2`; until upstream ships streaming passphrase IO, development may git-pin a fork under `[tool.uv.sources]`, which must be stripped before publish via `uv build --no-sources` / `check_dist_metadata`. — local `docs/adr/0003-age-encryption.md`
- Plan-4: “No git-pin of pyrage in published metadata”; “Publishing pyrage ourselves” is out of scope for 0.2.0 (Shawn / upstream). — local plan-4
- PyPI does not support private packages; private distribution is expected via a private index (docs mention `devpi`; Gitea provides an analogous PyPI registry). — [PyPI Help](https://pypi.org/help/); [Gitea PyPI registry](https://docs.gitea.com/usage/packages/pypi/)
- Gitea documents twine upload to `https://gitea.example.com/api/packages/{owner}/pypi` and install via `--index-url` with credentials; using `--extra-index-url` risks dependency-confusion because pip may prefer public PyPI. — [Gitea PyPI docs](https://docs.gitea.com/usage/packages/pypi/)
- You cannot upload the same name+version twice on Gitea without deleting first. — [Gitea PyPI docs](https://docs.gitea.com/usage/packages/pypi/)
- Forks commonly publish under a new distribution name (Pillow vs PIL pattern). — [packaging.python.org discussion](https://github.com/pypa/packaging.python.org/blob/main/source/discussions/distribution-package-vs-import-package.rst)
- Project AGENTS.md: never publish this package’s secrets; Gitea registry is temporary staging; PyPI comes after the three-package refactor. — local `AGENTS.md` / bmad context

### Inferences
- **Public PyPI fork under a new name:** dependency is a normal version pin in published metadata (compatible with `uv build --no-sources`). Shawn would own releases of that fork (or a thin companion package), separate from `l3io-wordpress-database` publish policy.
- **Private Gitea index:** fine for family-internal staging of a forked wheel, but every consumer (CI, Docker builds, backup) needs credentials / index config; unsuitable as the sole source for a package later published to public PyPI unless the fork is also mirrored to public PyPI.
- **Git pin only:** unblocks Epic 2 development (as plan-4 already allows) but cannot ship in published metadata; same as today’s config-pin pattern.
- Dependency-confusion: if the fork keeps distribution name `pyrage` on a private index while public PyPI has woodruffw’s `pyrage`, `--extra-index-url` setups are dangerous; a unique name reduces that risk.

### Gaps
- Exact uv/poetry semantics for declaring a second index in published lockfiles for end users of `l3io-wordpress-database` were not re-verified against current uv docs in this pass.
- Whether Shawn intends the encryption extra to stay public-PyPI-resolvable for third parties (vs family-only) is a product decision, not documented beyond “PyPI comes after refactor.”

## Building wheels (maturin) for manylinux / musllinux for WordPress Docker images

### Takeaway
`pyrage` already uses maturin + manylinux Docker for glibc wheels; musllinux is not shipped on PyPI today, so Alpine-based WordPress images would need an explicit musllinux build matrix (or sdist + compile-in-image), which any fork or thin PyO3 crate must also provide.

### Cited Findings
- `pyproject.toml` build backend is maturin (`maturin>=1.0,<2.0`); Python `>=3.10`. — [pyproject.toml](https://raw.githubusercontent.com/woodruffw/pyrage/main/pyproject.toml)
- Makefile `dist-pyrage` runs `docker run ... ghcr.io/pyo3/maturin build --release --sdist --strip --out dist`. — [Makefile](https://raw.githubusercontent.com/woodruffw/pyrage/main/Makefile)
- Release workflow builds Linux (x86_64 via maturin image), Linux ARM (ubuntu-22.04-arm), macOS universal2, Windows; publishes with Trusted Publishing (`pypa/gh-action-pypi-publish`). — [release.yml](https://raw.githubusercontent.com/woodruffw/pyrage/main/.github/workflows/release.yml)
- PyPI `pyrage` 1.4.0 artifacts include `manylinux_2_17_x86_64` / `aarch64`, macOS universal2, `win_amd64`, and an sdist — no `musllinux` wheel filenames in the release JSON. — [pypi.org/pypi/pyrage/1.4.0/json](https://pypi.org/pypi/pyrage/1.4.0/json)
- Maturin docs: Linux wheels for PyPI need manylinux (or zig); Rust ≥1.64 needs at least manylinux2014; `maturin-action` can set `manylinux: musllinux_1_2` for Alpine-compatible wheels. — [maturin distribution](https://www.maturin.rs/distribution.html); [maturin-action](https://github.com/PyO3/maturin-action)
- abi3 wheels (`abi3-py310` in Cargo.toml) mean one wheel covers many CPython versions ≥3.10, reducing matrix size. — [Cargo.toml](https://raw.githubusercontent.com/woodruffw/pyrage/main/Cargo.toml)

### Inferences
- Forking `pyrage` and reusing its Makefile/release workflow is the lowest-friction path to manylinux wheels matching what Docker Debian/Ubuntu WordPress images need.
- Alpine (musl) WordPress/php images are a separate matrix leg: stock PyPI `pyrage` does not cover them; a vendor/fork that only copies current upstream CI still leaves Alpine on sdist+Rust toolchain or without encryption.
- A thin dedicated PyO3 crate must recreate this CI; cost is real but smaller than maintaining the full pyrage surface if the crate only wraps passphrase IO.

### Gaps
- Which WordPress Docker base images the family actually runs (Debian slim vs Alpine) was not confirmed in this research pass; musllinux urgency depends on that.
- Cross-compile cost for `aarch64` musllinux under Gitea Actions (vs GitHub Actions ARM runners) was not measured.

## Alternative: small dedicated PyO3 crate wrapping Encryptor::with_user_passphrase + wrap_output

### Takeaway
A minimal maturin/PyO3 extension that only exposes streaming passphrase encrypt/decrypt is the cleanest long-term ownership model: MIT/`age` dual-license, no full-fork rebase tax, and a normal PyPI/Gitea package name that published metadata can pin without VCS sources.

### Cited Findings
- Passphrase encryption in the age Rust API is exactly `Encryptor::with_user_passphrase` then `wrap_output` / `finish`; decrypt uses `Decryptor` + `scrypt::Identity`. — [docs.rs Encryptor](https://docs.rs/age/latest/age/struct.Encryptor.html); [context7 rage/age examples](https://context7.com/str4d/rage/llms.txt)
- pyrage’s maintainer already demonstrated the in-memory passphrase path is a thin PyO3 wrapper around that API; streaming is the same wrapper with file-likes instead of `&[u8]` / `Vec`. — [yossarian.net pyrage post](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage); [lib.rs encrypt_io](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/lib.rs)
- `pyo3-file` / `PyFileLikeObject` is already how pyrage bridges Python IO; a new crate can depend on the same pattern. — [Cargo.toml](https://raw.githubusercontent.com/woodruffw/pyrage/main/Cargo.toml)
- Plan-4 rejected hand-rolling scrypt+STREAM and subprocess to stock `age` for passphrase (TTY / no safe secret channel). — local plan-4; ADR-0003

### Inferences
- Scope of a dedicated crate: two pyfunctions (~PR #171 passphrase body), error types, tests for streaming/RSS/`age -d`, maturin CI — likely smaller than a full pyrage fork.
- Security surface is “do we bump `age` promptly,” not “do we track SSH plugin bindings we don’t use.”
- l3io would own API stability; can name methods to match planned `encrypt_io`/`decrypt_io` without waiting on woodruffw.
- Still requires wheel building expertise (same as fork).

### Gaps
- No existing public “passphrase-only age PyO3” package was found in this search; greenfield maintenance estimate in person-hours is not sourced.
- Whether to include armor, async, or only binary streaming was not decided in project docs beyond mirroring recipient IO.

## Alternative: ctypes/cffi to rage, or call age from an l3io-owned Rust extension

### Takeaway
ctypes/cffi to the `rage` CLI binary is a poor fit (no C library ABI; passphrase CLI channel problems already rejected). Calling the `age` crate from an l3io-owned Rust/PyO3 extension is the same architectural class as the “small dedicated crate” option and is the supported library path.

### Cited Findings
- rage README: “Applications wishing to use rage as a library should use the `age` crate, which rage is built on top of.” No C FFI / shared-library API is documented there. — [str4d/rage](https://github.com/str4d/rage/)
- ADR-0003 / plan-4 reject stock `age` CLI subprocess for passphrase because of TTY-only / unsafe argv secret channel; kassiber’s abandoned path is cited. — local ADR-0003; plan-4
- Kassiber’s Python code documents that age binary passphrase mode is not safely supported via subprocess and falls back to in-memory pyrage (which buffers). — [kassiber age_cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/age_cli.py)
- pyrage itself is “pure Rust” with PyO3, chosen so crypto stays out of Python. — [yossarian.net post](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage)

### Inferences
- **ctypes/cffi to librage:** would require first writing and maintaining a C ABI shim around `age` — duplicate work of PyO3 with worse ergonomics for Python file-likes.
- **ctypes to `rage` executable:** reintroduces subprocess/secret-channel issues already rejected; not library IO.
- **l3io-owned PyO3 extension depending on `age`:** equivalent to the dedicated-crate alternative; can live in a sibling repo or under a private path, published as its own wheel package so `l3io-wordpress-database` only declares a versioned dependency (no VCS in metadata).

### Gaps
- Existence of third-party `age` C bindings (if any) was not exhaustively searched beyond rage’s own docs stating the Rust crate is the library API.

## Keeping recipient mode on stock pyrage (two deps) vs replacing pyrage entirely

### Takeaway
Two dependencies — stock `pyrage` for recipients/SSH/identity streaming plus a thin passphrase-streaming package — minimize divergence from woodruffw for the path that already works; a full fork/replacement consolidates installs but inherits the entire upstream maintenance and security surface.

### Cited Findings
- ADR-0003 defines two mutually exclusive modes: recipients/identities via pyrage, and passphrase via `pyrage.passphrase.encrypt_io`/`decrypt_io` once available. — local ADR-0003
- Recipient `encrypt_io`/`decrypt_io` already ship in stock pyrage 1.4.x `lib.rs`. — [lib.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/lib.rs)
- Passphrase module on main still lacks IO; only bytes APIs. — [passphrase.rs](https://raw.githubusercontent.com/woodruffw/pyrage/main/src/passphrase.rs)
- PyPI allows multiple distributions; import-name clashes occur if two distributions both provide `pyrage`. — [packaging discussion](https://github.com/pypa/packaging.python.org/blob/main/source/discussions/distribution-package-vs-import-package.rst)

### Inferences
- **Two-deps (recommended ownership shape if upstream stays closed):** `encryption` extra becomes something like `pyrage>=1.4,<2` plus `l3io-age-passphrase>=…,<2` (names illustrative). Python code routes `passphrase=` to the thin package and recipients to stock pyrage. Divergence risk limited to passphrase path.
- **Full fork replacing pyrage:** single native wheel; must re-ship SSH/plugin/x25519/tag support or drop features the family uses; every upstream CVE/API fix requires cherry-pick; published metadata pins the fork name instead of `pyrage`.
- **Vendored patched wheel inside the database repo:** avoids a second package name but forces multi-platform wheel commits or platform-specific builds; awkward with abi3 multi-arch; still needs LICENSE retention; poor fit for PyPI consumers unless wheels are attached as package data (large, platform-tagged hell).
- Import design: thin package should **not** install as `pyrage` if stock pyrage remains a dependency.

### Gaps
- Whether backup/database currently rely on pyrage SSH recipients (vs age x25519 only) determines how painful a “replace pyrage” fork would be; not re-audited in this pass.

## Long-term: security updates when rage/age crates bump

### Takeaway
Whoever owns the binding that links `age` must watch crates.io/`age` advisories and cut new wheels; a thin passphrase-only crate or full fork both take that duty for their binary, while stock `pyrage` continues to cover recipient-mode bumps if left as a separate dependency.

### Cited Findings
- `age` on crates.io is still marked BETA in the summary; current version observed 0.12.1, MSRV 1.74, actively downloaded; license MIT OR Apache-2.0. — [crates.io/crates/age](https://crates.io/crates/age)
- pyrage pins a concrete `age` version in Cargo.toml (`0.12.1`) rather than a wide range, so upstream pyrage releases are the usual way Python users get `age` updates. — [Cargo.toml](https://raw.githubusercontent.com/woodruffw/pyrage/main/Cargo.toml)
- PyPI release JSON for 1.4.0 listed `"vulnerabilities": []` at fetch time (not a guarantee of absence of Rust-side issues). — [pypi JSON](https://pypi.org/pypi/pyrage/1.4.0/json)
- Maturin/PyO3 wheels embed the compiled Rust crypto; users cannot `pip install -U age` independently — a new wheel build is required. — [maturin distribution](https://www.maturin.rs/distribution.html); [pyrage architecture post](https://blog.yossarian.net/2022/07/25/age-encryption-in-python-with-pyrage)

### Inferences
- **Stock pyrage + thin passphrase crate:** monitor two release trains; recipient CVEs fixed by bumping `pyrage`; passphrase CVEs fixed by bumping the thin crate’s `age` pin and rebuilding wheels. Failure mode is asymmetric neglect of the thinner, less-watched package.
- **Full pyrage fork:** one release train owned by Shawn; must track woodruffw merges **and** `age`/`pyo3` upgrades; lagging upstream increases divergence and missed fixes.
- **Vendored frozen wheel:** worst security posture — no automatic update path until someone rebuilds and recommit/reuploads.
- Process need (whichever option): Dependabot/renovate on `Cargo.toml`, CI wheel rebuild, and a SemVer policy for the owned package so `l3io-wordpress-database[encryption]` can raise floors cleanly.

### Gaps
- No historical count of security advisories for `age`/`rage` was compiled; severity of “must track betas” is qualitative.
- Whether the family already has Rust release automation outside this repo is unknown here.

## Cross-cutting comparison (for the report writer)

| Option | Publishable without VCS deps | Maint. cost | Divergence from woodruffw | Wheel CI burden | Notes |
|---|---|---|---|---|---|
| Git-pin fork tip (`uv.sources`) | No (dev only) | Low short-term | High if long-lived | None beyond upstream | Already allowed pre-publish |
| Full public fork, new PyPI name | Yes | High (rebase whole tree) | High | Same as pyrage (+ musl?) | MIT-ok; owns all features |
| Fork on private Gitea index only | Staging yes / public PyPI consumers no | High | High | Same | Auth + confusion risk; temp staging |
| Thin PyO3 passphrase crate | Yes | Medium-low | Low (recipients stay on stock) | New but small matrix | Best fit for two-mode ADR |
| Replace pyrage entirely with owned binding | Yes | High | N/A (leave upstream) | Full age feature set | Only if dropping stock pyrage |
| ctypes/cffi to rage | N/A | High / unsafe | N/A | Binary packaging | No C ABI; CLI rejected |
| Vendored patched wheel in-repo | Awkward | High (stale binaries) | High | Manual per-platform | Weak update story |

PR #171 status as of 2026-10-25: closed, unmerged, locked as spam — treat upstream acceptance as unavailable for planning.
