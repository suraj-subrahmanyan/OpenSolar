# OpenJiuwen Solar

OpenJiuwen Solar is a Python/bash harness for running a local multi-agent
software cockpit with Codex or Claude Code as the selected pane runtime. It
opens real agent processes in tmux panes, accepts natural-language work,
records the work as file-backed sprint/runtime artifacts, dispatches to live
agents, and keeps human approval gates in the loop.

Solar is not a finished autonomous cloud service and not a TypeScript
orchestrator product. The working product today is the local harness plus the
installer/lifecycle tooling around it.

## Quick Start

Shell installer:

```bash
curl -fsSL https://raw.githubusercontent.com/suraj-subrahmanyan/OpenSolar/v1.0.0-rc.9/get-solar.sh | bash -s -- --yes --components kernel,harness
~/.solar/bin/solar doctor
```

Python wrapper from the current release branch:

```bash
pipx install "git+https://github.com/suraj-subrahmanyan/OpenSolar.git@v1.0.0-rc.9#subdirectory=distribution/pipx"
openjiuwen-solar install --yes --components kernel,harness
openjiuwen-solar doctor
```

After the owner publishes the prepared PyPI package, the wrapper install command
becomes:

```bash
pipx install openjiuwen-solar
openjiuwen-solar install --yes --components kernel,harness
```

Interactive install is also supported:

```bash
curl -fsSL https://raw.githubusercontent.com/suraj-subrahmanyan/OpenSolar/v1.0.0-rc.9/get-solar.sh | bash
```

The installer writes only under `~/.solar` and `~/.claude/solar`, records an
install receipt, and gives you `solar doctor`, `solar update`, `solar repair`,
`solar backup`, and `solar uninstall`.

## What You Get

The real, working Solar surface is:

- a four-pane tmux cockpit through `solar harness start`;
- natural-language intake through `solar harness intake "..."`;
- selectable Codex or Claude Code pane runtimes, with provider-specific
  authentication and fail-closed routing;
- human gates such as `solar harness plan-verdict` and
  `solar harness eval-verdict`;
- per-role model selection through `solar harness models show` and related
  `models` verbs;
- background tasks through `solar harness bg`;
- program analytics through `solar harness stats`;
- cross-machine migration/deploy helpers through `solar harness migrate` and
  `solar harness deploy`;
- deterministic local status views through `solar status`, `solar doctor`, and
  `solar ui`;
- optional knowledge integrations such as the Obsidian wiki and RAGFlow
  adapters.

Some code in `core/` is roadmap scaffolding or compatibility glue. It is kept in
the repository, but the README and CLI surfaces should not treat it as a fully
working autonomous orchestrator.

## Language Policy

Solar v1.0 ships with a Chinese-first persona and English lifecycle commands.
Commands, docs, installer output, and public-facing help are being made English
first. The operative kernel/persona content still contains Chinese by design;
full bilingual kernel translation is post-v1.0 work.

## Platform Support

| Platform | v1.0 status | Notes |
|---|---|---|
| macOS | Primary | Main target for the tmux cockpit. Bash 4+, tmux, jq, Python 3, git, and either Codex or Claude Code are needed for live harness work. The native DMG still requires real-machine release proof. |
| Linux | Supported | Installer/lifecycle, deterministic smoke, and one installed ordinary-prompt Codex path are exercised. Live work still depends on the selected runtime's local auth/trust/quota. |
| Windows / WSL2 | Experimental (WSL2) | The desktop app and `install.ps1` auto-provision WSL2 and install the runtime inside it (pinned release channel, prerequisite bootstrap, reboot-resume, logon autostart); the host reaches it over localhost. Covered by deterministic gates + code review; full real-hardware confirmation is owner-manual — see [docs/WINDOWS.md](docs/WINDOWS.md). |

## Basic Workflow

Verify the install:

```bash
solar status
solar doctor
```

Check the harness launch requirements:

```bash
solar harness preflight
```

Choose Codex or Claude Code in Dashboard **Settings > Runtime**, then
authenticate only that selected runtime (`codex login --device-auth` for Codex,
or `claude` for Claude Code). Start the settings dashboard with:

```bash
solar harness status-server start
```

Start the Product Delivery cockpit:

```bash
solar harness start /path/to/project
```

Inside the cockpit, trust/login prompts and provider quota limits are real
operator boundaries. Solar reports the selected runtime separately and does
not treat another installed provider as a valid fallback. Deterministic
plumbing status is not proof of a fresh live response; that proof exists only
after the selected panes produce a real result on the machine.

Submit a task:

```bash
solar harness intake "Add a failing test for the parser bug, fix it, and show the evidence."
```

Approve or reject gates:

```bash
solar harness plan-verdict <sprint-id> approve "scope looks right"
solar harness eval-verdict <sprint-id> pass "tests and evidence accepted"
```

Choose or inspect models:

```bash
solar harness models show
solar harness models set-main opus --apply
```

### Governed Planning (default on)

Free-prompt tasks submitted through intake run under the governed generic
path by default: the planner's task graph is compile-checked and stamped
with a plan certificate before any builder runs, gate results are recorded
in a per-sprint gate ledger, and node completion claims are verified
against real artifacts. No configuration is needed — a fresh install is
governed out of the box.

To inspect the resolved state on any machine:

```bash
python3 ~/.solar/harness/lib/plan_validator.py env-status
```

An explicit `SOLAR_PLAN_VALIDATOR=0` or `SOLAR_GATE_LEDGER=0` in the
environment disables the corresponding layer (supported but discouraged —
it removes the evidence checks). Hand-authored task graphs and pre-existing
workflows without the intake birth marker are grandfathered and keep their
legacy behavior.

## Install Details

See:

- [INSTALL.md](INSTALL.md) for components, flags, install layout, and lifecycle
  commands.
- [docs/FIRST-SESSION.md](docs/FIRST-SESSION.md) for the first install,
  cockpit, intake, and model-selection walkthrough.
- [docs/COMPONENTS.md](docs/COMPONENTS.md) for the generated component list.
- [docs/UNINSTALL.md](docs/UNINSTALL.md) for residue-free uninstall behavior.
- [docs/WINDOWS.md](docs/WINDOWS.md) for the WSL2 bootstrap path (experimental).

Default install:

```bash
./install.sh --yes --components kernel,harness
```

Optional components include `core-runtime`, `skills-md`, `skills-office`,
`skills-obsidian`, `skills-calendar`, `skills-browser`, `codex-bridge`,
`mempalace`, `daemons`, and `solar-max`. Use:

```bash
./install.sh --list-components
```

## Development And Release

This repository is still being prepared for public v1.0 packaging. Do not treat
local branches, release candidates, or the moving `stable` branch as registry
publication. The owner performs irreversible release actions: PyPI upload,
GitHub Release creation, release asset upload, tags, and public ref updates.

Contributors should read [AGENTS.md](AGENTS.md) before editing. Release
preparation remains owner-gated and uses the maintainer checklist in this repo.

## License

MIT. See [LICENSE](LICENSE).
