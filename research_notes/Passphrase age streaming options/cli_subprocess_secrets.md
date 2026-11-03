# Stock age/rage CLI subprocess for passphrase streaming

Research date: 2026-10-25. Local host had distro `age` 1.2.1 (no batchpass); official FiloSottile/age **v1.3.2** linux-amd64 release was downloaded and exercised for verification.

## How does `age -e -p` / `age -d` accept passphrases non-interactively?

### Takeaway
Stock `age -p` / auto-detected passphrase decrypt remains **TTY-interactive only**; non-interactive passphrase use was deliberately *not* added to the core CLI. Since **age v1.3.0** (2025-12-27), the supported automation path is the separate **`age-plugin-batchpass`** invoked as `age -e -j batchpass` / `age -d -j batchpass`, reading `AGE_PASSPHRASE` or `AGE_PASSPHRASE_FD` (not argv).

### Cited Findings
- Man page for core `age` (Ubuntu 1.2.1): `-p/--passphrase` encrypts with a passphrase "**requested interactively from the terminal**"; decrypt of passphrase files "**requested interactively**". No passphrase-file or env flags on the core binary. — local `man age`; consistent with [FiloSottile/age README/usage](https://github.com/FiloSottile/age)
- Builtin env-var PR for the core CLI was **closed without merge**; maintainer implemented the feature as the batchpass plugin instead. — [FiloSottile/age#520](https://github.com/FiloSottile/age/pull/520) (closed 2025-12-24 with pointer to batchpass)
- Related older requests for `--passphrase-fd` / non-TTY passphrase remain answered by the plugin, not by flags on `age -p`. — [FiloSottile/age discussion #257](https://github.com/FiloSottile/age/discussions/257); [issue #603](https://github.com/FiloSottile/age/issues/603) (stdin passphrase still not a core CLI feature)
- **v1.3.0 release notes**: "Non-interactive passphrase input … is now available through the **batchpass plugin**"; authors still warn most uses should prefer native keys or passphrase-encrypted identities. — [age v1.3.0 release](https://github.com/FiloSottile/age/releases/tag/v1.3.0); also summarized at [newreleases.io mirror](https://newreleases.io/project/github/FiloSottile/age/release/v1.3.0)
- Plugin usage (documented):
  - `AGE_PASSPHRASE=secret age -e -j batchpass file.txt > file.txt.age`
  - `AGE_PASSPHRASE=secret age -d -j batchpass file.txt.age > file.txt`
  - `AGE_PASSPHRASE_FD=3 age -e -j batchpass file.txt 3< passphrase.txt > file.txt.age`
  - Env vars mutually exclusive; FD path strips trailing newlines. — [age-plugin-batchpass(1) Arch man](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en); [OpenSUSE man](https://manpages.opensuse.org/Tumbleweed/age/age-plugin-batchpass.1.en.html); [plugin source](https://raw.githubusercontent.com/FiloSottile/age/main/cmd/age-plugin-batchpass/plugin-batchpass.go)
- Plugin encrypt path calls `age.NewScryptRecipient(pass)` and decrypt unwraps stanza type `"scrypt"` — i.e. **stock scrypt recipient format**, not a proprietary plugin stanza in the file header. — [plugin-batchpass.go](https://raw.githubusercontent.com/FiloSottile/age/main/cmd/age-plugin-batchpass/plugin-batchpass.go); [scrypt.go](https://github.com/FiloSottile/age/blob/main/scrypt.go); [C2SP age.md scrypt section](https://github.com/C2SP/C2SP/blob/main/age.md)
- Empirical (v1.3.2 linux-amd64 tarball, 2026-10-25): encrypt with `-j batchpass` produced header bytes containing `-> scrypt …`; `age-inspect` reported recipient type `"scrypt"`; round-trip via `AGE_PASSPHRASE` and via `AGE_PASSPHRASE_FD=3` succeeded. Plugin binary must be discoverable on **`$PATH`** as `age-plugin-batchpass` (presence next to `age` alone is insufficient). — local verification against [v1.3.2 release assets](https://github.com/FiloSottile/age/releases)
- Community workarounds that are **not** official: `expect` scripts driving the TTY prompt (fragile; poor Windows story). — [str4d/rage#550](https://github.com/str4d/rage/issues/550); comments on [FiloSottile/age#520](https://github.com/FiloSottile/age/pull/520)

### Inferences
- As of 2026-10-25, ADR-0003’s claim that **stock** `age -p` is “TTY-only / no safe secret channel” is still true for the **core** binary and for distro packages at ≤1.2.x.
- A **CLI-based** non-interactive path *does* exist if the deployment ships **age ≥ 1.3** *and* `age-plugin-batchpass` on PATH, using env or (preferably) an inherited FD — not `age -p` itself.
- Files produced by batchpass are stock-age passphrase files; operators can still recover with interactive `age -d` (TTY prompt) without the plugin.

### Gaps
- Distro packaging lag: Ubuntu/local host still on 1.2.1 without the plugin; no survey of which Linux distros ship 1.3.x + batchpass as of today.
- Whether interactive `age -d` (without `-j`) will refuse or confuse when `-i` is also passed alongside a scrypt file is documented for identities, but exact UX when mixing `-j batchpass` with other identities was not exhaustively tested here.

## Do FiloSottile/age or str4d/rage document safe secret passing?

### Takeaway
Official guidance actively discourages scripting passphrases: prefer X25519 identities (possibly held in env/CI secrets) or passphrase-**encrypted identity files**; when batchpass is used, docs warn about shell history and multi-user leakage. Neither project documents putting the passphrase on argv; batchpass exposes env and FD channels only.

### Cited Findings
- batchpass help/man opens with "**WARNING: IN 90% OF CASES, YOU DON'T NEED THIS PLUGIN**" and recommends encrypting to a native identity (`age -e -i key.txt`) or storing `AGE-SECRET-KEY-…` in env/`<(echo …)` for non-interactive work. — [plugin-batchpass.go usage string](https://raw.githubusercontent.com/FiloSottile/age/main/cmd/age-plugin-batchpass/plugin-batchpass.go); [Arch man](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en)
- Same docs: “care should be taken not to let the password be persisted in the **shell history** or leaked to other users on multi-user systems.” — [Arch man](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en)
- Historical maintainer position (rage, 2021): native CLI would **not** support scriptable passphrase inputs; plugins could. — [str4d/rage#215](https://github.com/str4d/rage/issues/215)
- 2026: rage maintainer rejected `AGE_ASKPASS` for programmatic passphrases and pointed users to **`age-plugin-batchpass`**. — [str4d/rage#617](https://github.com/str4d/rage/pull/617) (closed 2026-08-16)
- rage issue for non-interactive passphrase remains open; commenters still suggest expect/pinentry rather than a rage-native secret flag. — [str4d/rage#550](https://github.com/str4d/rage/issues/550) (updated 2026-04-19)
- General Unix guidance: secrets on **argv** appear in `/proc/<pid>/cmdline` / `ps`; **environ** is better than argv but still readable by same-UID (and historically sometimes others); **dedicated FD / stdin** is preferred. — [Security SE #190071](https://security.stackexchange.com/questions/190071/when-running-shell-scripts-is-it-safer-to-pass-sensitive-information-using-stdi); [SO openssl passin patterns](https://stackoverflow.com/questions/9625844/passing-key-material-to-openssl-commands); [SO hiding argv secrets](https://stackoverflow.com/questions/3830823/hiding-secret-from-command-line-parameter-on-unix)

### Inferences
- Documented “safe enough” CLI secret channel for age automation in 2026 is **`AGE_PASSPHRASE_FD`** (or carefully scoped `AGE_PASSPHRASE`), never argv and never `echo secret | age -d` while stdin is the ciphertext.
- Authors’ preferred *design* for CI is still **identity strings**, not passphrases, because scrypt is slow and humans choose weak secrets.

### Gaps
- No first-party age doc that ranks `AGE_PASSPHRASE` vs `AGE_PASSPHRASE_FD` threat models beyond the man-page warning.
- No official Python/subprocess cookbook from FiloSottile or str4d.

## Can you stream encrypt `mysqldump | age … > dump.age` with bounded memory?

### Takeaway
Yes for the **payload path**: age is designed for Unix pipes and processes ciphertext in **64 KiB STREAM chunks**. Passphrase/scrypt work is a **fixed** cost on the header (expensive CPU/time, not proportional to dump size). Adversarial or pathological **headers** can still force large buffers; normal single-scrypt dumps do not.

### Cited Findings
- Official usage example pipes archives: `tar cvz ~/data | age -r age1… > data.tar.gz.age`. — [FiloSottile/age](https://github.com/FiloSottile/age) / local `age --help`
- age STREAM chunk size is 64 KiB; large-file decrypt emits output after ~header + one chunk rather than buffering the whole file. — [FiloSottile/age#176](https://github.com/FiloSottile/age/pull/176) (str4d comment)
- Spec/implementation notes: headers are buffered for MAC; a malicious endless-recipient header drove age past **17 GB RSS** in one report; normal headers are small. — [C2SP/C2SP#28](https://github.com/C2SP/C2SP/issues/28)
- Empirical: `dd … 50MiB | AGE_PASSPHRASE=s age -e -j batchpass | AGE_PASSPHRASE=s age -d -j batchpass | wc -c` returned **52428800** (exact) under age v1.3.2. — local verification 2026-10-25
- Project ADR already assumes streaming with bounded RSS for age payloads, with a large fixed scrypt cost in passphrase mode. — repo `docs/adr/0003-age-encryption.md`

### Inferences
- `mysqldump | AGE_PASSPHRASE_FD=… age -e -j batchpass > dump.age` is a viable multi-GB pattern **if** the plugin is present and the passphrase channel is set up without consuming stdin.
- Peak RSS is not “constant bytes” under adversarial ciphertext headers; for trusted self-produced dumps it is effectively bounded aside from scrypt scratch space.

### Gaps
- No measurement here of peak RSS during a multi-GB batchpass encrypt (only functional 50 MiB pipe test).
- Armor (`-a`) to a TTY can buffer; binary stdout to a file/pipe is the relevant dump path.

## What about decrypt into a mysql client pipe?

### Takeaway
The same streaming model applies: `age -d … | mysql …` (or `mariadb`) should feed plaintext as STREAM chunks authenticate. Wrong passphrase fails at header unwrap before useful plaintext; mid-stream corruption can leave partial SQL already applied — operational staging remains advisable.

### Cited Findings
- age decrypt writes authenticated 64 KiB chunks as they verify; truncated/corrupt payload fails after some plaintext may already have been written. — [FiloSottile/age#176](https://github.com/FiloSottile/age/pull/176); analogous streaming semantics described for other age implementations e.g. [Crypt::Age decrypt_filehandle](https://metacpan.org/pod/Crypt::Age)
- CLI refuses decrypted **binary** output to a terminal (v1.3+ usability note) but pipes to another process are the intended composable path. — [age v1.3.0 release](https://github.com/FiloSottile/age/releases/tag/v1.3.0)
- Non-interactive decrypt: `AGE_PASSPHRASE_FD=3 age -d -j batchpass dump.age 3<<<"$pass" | mysql …` keeps ciphertext on stdin of age and passphrase on a separate FD. — [batchpass man FD example](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en)

### Inferences
- Decrypt-into-mysql is fine for pipes; callers that need all-or-nothing DB state should still decrypt to a staging file/DB (as this package already plans) because STREAM cannot rewind committed SQL.
- Do not put the dump on age’s stdin *and* try to feed the passphrase on the same stdin.

### Gaps
- No live `mysqldump`/`mysql` integration test run in this research pass.
- Exact age behavior when stdout is a pipe that stops early (broken pipe / SIGPIPE) under batchpass was not measured.

## Security pitfalls: argv, env, TTY, echo

### Takeaway
Never put the passphrase on argv. Prefer `AGE_PASSPHRASE_FD` over `AGE_PASSPHRASE`. Avoid expect/TTY spoofing in automation. Shell history and same-UID `/proc` remain the main leak surfaces for env-based approaches.

### Cited Findings
- Argv is visible via `/proc/<pid>/cmdline` and `ps`; overwriting argv later does not fully fix the race. — [SO #6607675](https://stackoverflow.com/questions/6607675/shell-script-password-security-of-command-line-parameters); [SO #3830823](https://stackoverflow.com/questions/3830823/hiding-secret-from-command-line-parameter-on-unix)
- Linux `/proc/<pid>/environ` is typically restricted to same euid/root, but still exposed to co-resident same-user processes and to root; wiping is racy. — [Unix SE #302948](https://unix.stackexchange.com/questions/302948/change-proc-pid-environ-after-process-start); [Security SE #190071](https://security.stackexchange.com/questions/190071/when-running-shell-scripts-is-it-safer-to-pass-sensitive-information-using-stdi)
- batchpass documents both env and FD; warns about **shell history** and multi-user leakage. Prefix form `AGE_PASSPHRASE=secret age …` is especially history-hostile if typed interactively. — [Arch man](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en)
- Core `age -p` confirms passphrase interactively (echo off on TTY); without a TTY, encryption/decryption that needs a prompt fails — motivating expect hacks that reintroduce TTY and logging risks. — local `man age`; [rage#550 expect examples](https://github.com/str4d/rage/issues/550)
- Child processes inherit env unless cleared; Python `subprocess` should pass a minimal `env=` and `pass_fds=` for the passphrase FD, and avoid `shell=True` (history/word-splitting). — general practice reflected in [SO openssl + Python passin](https://stackoverflow.com/questions/9625844/passing-key-material-to-openssl-commands)
- Plugin binary is a second process; with `AGE_PASSPHRASE` set, **both** `age` and `age-plugin-batchpass` inherit the secret in their environments. — inferred from plugin reading `os.Getenv("AGE_PASSPHRASE")` in [plugin-batchpass.go](https://raw.githubusercontent.com/FiloSottile/age/main/cmd/age-plugin-batchpass/plugin-batchpass.go)

### Inferences
- From Python, the least-bad CLI secret channel is: create an `os.pipe()`, write the passphrase bytes, close the write end, `Popen([…, "-j", "batchpass"], env={…, "AGE_PASSPHRASE_FD": str(r)}, pass_fds=(r,), stdin=dump_pipe, stdout=out_pipe)`.
- `AGE_PASSPHRASE` in the child env is acceptable in single-tenant containers with short lifetime, but is weaker than FD on multi-user hosts.
- Expect-based automation does **not** meet the “no TTY / Docker-CI” bar cleanly.

### Gaps
- Whether age or the plugin clears `AGE_PASSPHRASE` from its address space after reading was not audited in source beyond the getenv call.
- Windows visibility of process environment vs Linux `/proc` differs; not fully compared here.

## Packaging: shipping binary vs host; Go vs Rust; Windows

### Takeaway
Relying on host `age` is fragile (distros often lag before 1.3 / omit plugins). Official Go **age** release tarballs/zips for v1.3.2 already include `age-plugin-batchpass` alongside `age` for linux/darwin/freebsd/windows. **rage** remains a separate Rust CLI with plugin protocol support but **no** first-class passphrase automation flags; Windows users historically preferred rage for interactive UX, while automation now centers on the Go plugin.

### Cited Findings
- Latest release at research time: **age v1.3.2** (2026-08-29) assets include `linux-amd64`, `linux-arm64`, `darwin-*`, `freebsd-amd64`, `windows-amd64`, `windows-arm64`. — GitHub Releases API / [FiloSottile/age releases](https://github.com/FiloSottile/age/releases)
- Inspected `age-v1.3.2-linux-amd64.tar.gz` contents: `age`, `age-keygen`, `age-inspect`, **`age-plugin-batchpass`**, plus pq/tag compatibility plugins. — local tarball listing
- Local Ubuntu package: `age` **1.2.1-1build1** — **no** `age-plugin-batchpass` on PATH. — `dpkg -l age`; `age --version`
- rage: Rust implementation; ships plugin library/docs for building/using age plugins with rage clients. — [str4d/rage](https://github.com/str4d/rage); [docs.rs age-plugin](https://docs.rs/crate/age-plugin/latest/source/README.md)
- Windows: age ships official Windows zips; issue authors still report rage interactive UX as better on Windows; expect-based passphrase scripting fails natively on Windows. — [age v1.3.0 assets](https://github.com/FiloSottile/age/releases/tag/v1.3.0); [rage#550](https://github.com/str4d/rage/issues/550)
- Plugin discovery requires `age-plugin-<name>` **on PATH**, not merely adjacent to the `age` binary. — local failure mode when cwd held the plugin but PATH did not; matches age plugin error text

### Inferences
- A Python package that shells out must either **vendor/pin** age≥1.3.2 + ensure the extract dir is on PATH (or install the plugin name), or document a hard host dependency that many CI images will not meet yet.
- Shipping only `age` without `age-plugin-batchpass` reverts passphrase automation to TTY-only.
- rage alone does not replace batchpass; at best `rage -j batchpass` plus the Go (or any) plugin binary on PATH.

### Gaps
- Exact rage CLI flag parity for `-j` / plugin invocation was not re-verified with a local rage binary (rage not installed on the research host).
- Homebrew/winget/apt package contents for 1.3.x + plugins not enumerated OS-by-OS.
- Code-signing / supply-chain story for vendoring age binaries in a Python wheel was not researched.

## Prior art: kassiber and abandoned CLI passphrase paths

### Takeaway
Kassiber explicitly **rejects** stock age/rage subprocess for passphrase mode (TTY / no safe channel), keeps the **binary for recipient-mode streaming**, and uses **pyrage** for passphrase — matching this package’s ADR-0003 rejection rationale. Other projects resorted to expect, custom AGE_PASSPHRASE forks, or deterministic keygen foot-guns before batchpass existed.

### Cited Findings
- Kassiber `age_cli.py`: prefers `age`/`rage` on PATH for streaming; for `mode="passphrase"` **prefers pyrage** even if a binary exists; `encrypt_age_stream` **raises** if asked to use binary passphrase mode (“not safely supported via subprocess yet”). — [kassiber/backup/age_cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/age_cli.py)
- Kassiber’s own CLI never puts DB/backup passphrases on argv; uses TTY `getpass` or `--*-passphrase-fd`. — [kassiber/secrets/prompt.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/secrets/prompt.py); [kassiber/backup/cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/cli.py)
- This repo’s ADR-0003 options table rejected “Stock age CLI subprocess for passphrase” as “TTY-only / no safe secret channel on argv”; plan 4 same rejection. — `docs/adr/0003-age-encryption.md`; `_bmad-output/planning-artifacts/plans/2026-10-20-plan-4-passphrase-stream.md`
- Pre-batchpass ecosystem pressure produced expect scripts, unmerged env PRs, and projects like deterministic age keygen from passwords (discouraged). — [discussion #257](https://github.com/FiloSottile/age/discussions/257); [PR #520](https://github.com/FiloSottile/age/pull/520); [rage#550](https://github.com/str4d/rage/issues/550)

### Inferences
- Kassiber’s abandonment predates or ignores batchpass; the **architectural split** (CLI stream for recipients, library for passphrase) remains a strong prior-art pattern even after batchpass, because packaging/PATH/plugin complexity remains.
- If revisiting the ADR solely due to batchpass, the decision is no longer “impossible,” but “extra binary + PATH + env/FD plumbing vs in-process pyrage.”

### Gaps
- Kassiber git history was not checked for post-batchpass updates after commit `7bf8dbbc`.
- No other production Python mysqldump|age tools beyond kassiber were deeply surveyed.

## age vs rage CLI feature parity for passphrase

### Takeaway
**Parity on interactive passphrase** (`-p` / auto-detect decrypt with TTY). **No parity on non-interactive**: only FiloSottile’s **batchpass plugin** is the blessed automation path; rage maintainers defer to that plugin rather than adding rage-native env/FD flags. Format interoperability for scrypt files remains shared.

### Cited Findings
- Both implement the age format including scrypt passphrase recipients per C2SP. — [C2SP age.md](https://github.com/C2SP/C2SP/blob/main/age.md)
- age: interactive `-p`; non-interactive via `-j batchpass` + `AGE_PASSPHRASE` / `AGE_PASSPHRASE_FD` since v1.3.0. — [v1.3.0 release](https://github.com/FiloSottile/age/releases/tag/v1.3.0); [batchpass man](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en)
- rage: closed native passphrase-from-FD request in 2021 in favor of plugins / encrypted identities. — [rage#215](https://github.com/str4d/rage/issues/215)
- rage: 2026 PR for `AGE_ASKPASS` closed; maintainer: use `age-plugin-batchpass`. — [rage#617](https://github.com/str4d/rage/pull/617)
- rage#550 still open requesting non-interactive passphrase UX. — [rage#550](https://github.com/str4d/rage/issues/550)
- Plugin protocol is shared; rage can act as a plugin **client**. — [age-plugin README / docs.rs](https://docs.rs/crate/age-plugin/latest/source/README.md); [c2sp.org/age-plugin](https://c2sp.org/age-plugin)
- Empirically, batchpass output is a normal `scrypt` file → decryptable by stock `age -d` (interactive) and by library implementations such as pyrage passphrase APIs that speak scrypt. — local `age-inspect` + [plugin uses NewScryptRecipient](https://raw.githubusercontent.com/FiloSottile/age/main/cmd/age-plugin-batchpass/plugin-batchpass.go)

### Inferences
- Choosing rage over age does **not** improve passphrase automation; you still need `age-plugin-batchpass` (or pyrage/in-process).
- Interop goal “existing pyrage recipient mode + passphrase dumps decryptable by stock age” is satisfied by batchpass **or** pyrage passphrase IO, because both emit scrypt-only headers.
- Feature parity summary (2026-10-25):

  | Capability | age core | age + batchpass | rage core | rage + batchpass |
  |---|---|---|---|---|
  | Interactive passphrase encrypt/decrypt | yes | yes | yes | yes |
  | Non-interactive passphrase (env/FD) | no | yes | no | yes (via plugin) |
  | Streaming stdin/stdout | yes | yes | yes (design) | yes (design) |
  | Stock scrypt file format | yes | yes | yes | yes |

### Gaps
- Side-by-side rage+batchpass encrypt/decrypt was not run locally (no rage binary).
- Work-factor defaults / max-work-factor flag differences between age CLI interactive path, batchpass env knobs, and pyrage were not fully tabulated.

## Objective check: can a CLI-based path meet the criteria?

### Takeaway
**Conditionally yes** with age ≥ 1.3.2 **and** `age-plugin-batchpass` on PATH using `AGE_PASSPHRASE_FD` (not argv): streaming, stock age format, Docker/CI non-interactive, and scrypt-interop with pyrage passphrase files. **Stock `age -p` alone still fails** the non-interactive / no-TTY requirement that motivated ADR-0003. Packaging and same-UID env leakage remain material cons versus in-process pyrage.

### Cited Findings
- Criteria mapping draws on findings above: streaming ([age help](https://github.com/FiloSottile/age), [#176](https://github.com/FiloSottile/age/pull/176)); format ([C2SP](https://github.com/C2SP/C2SP/blob/main/age.md), local inspect); secret channel ([batchpass man](https://man.archlinux.org/man/extra/age/age-plugin-batchpass.1.en)); TTY-only core (`man age`, [#520](https://github.com/FiloSottile/age/pull/520)); prior rejection ([ADR-0003](../../docs/adr/0003-age-encryption.md)); kassiber parallel ([age_cli.py](https://github.com/bitcoinaustria/kassiber/blob/7bf8dbbc/kassiber/backup/age_cli.py)).

### Inferences
- “Is the 2024–early-2026 rejection still true in 2026-10?” → **True for bare `age`/`rage` passphrase flags**; **false as an absolute** if the batchpass plugin is treated as an allowed dependency.
- For this package, CLI subprocess passphrase is a **viable alternative architecture**, not a free lunch: two binaries, PATH wiring, FD plumbing, and weaker secret hygiene than keeping the passphrase inside the Python process for pyrage.

### Gaps
- Product decision (stick with pyrage vs adopt batchpass) is out of scope for research-only notes.
