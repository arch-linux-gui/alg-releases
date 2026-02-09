# ALG Release Automation

Release automation tool for [Arka Linux GUI](https://arkalinuxgui.org/). Automates ISO building, uploading, checksumming, GitHub releases, and website updates.

## Prerequisites

- Arch Linux with `archiso` installed
- Python 3.10+
- `rsync`, `ssh` (for SourceForge uploads)
- `qemu-full` (optional, for VM testing)

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Full release pipeline
python -m release_tool --all --version 2026.02

# Dry run (no side effects)
python -m release_tool --all --dry-run
```

## Stages

Each stage can be run independently or combined. Use `--all` to run everything sequentially.

| Flag | Stage | Description |
|------|-------|-------------|
| `--build` | 1 | Clone/pull edition repos, build ISOs via `mkarchiso` |
| `--test` | 2 | Pause for manual ISO testing |
| `--upload` | 3 | Upload ISOs to SourceForge via `rsync` |
| `--checksum` | 4 | Generate SHA-256 checksums |
| `--changelog` | 5 | Auto-generate changelog from git commits since last tag |
| `--github-release` | 6 | Create tagged GitHub release with notes + checksums |
| `--website` | 7 | PR to update `Isodata.ts` and `ReleasePage.tsx` on web repo |

## Options

| Flag | Description |
|------|-------------|
| `--version VERSION` | Override release version (default: `YYYY.MM` from date) |
| `--config PATH` | Path to config file (default: `./config.yaml`) |
| `--dry-run` | Print commands without executing destructive operations |
| `--qemu` | Launch QEMU VMs for ISO testing (use with `--test`) |
| `--no-confirm` | Skip confirmation prompts (for scripted/CI use) |
| `-v, --verbose` | Debug logging |

## Usage Examples

```bash
# Build ISOs only
python -m release_tool --build

# Build and test with QEMU VMs
python -m release_tool --build --test --qemu

# Generate changelog, edit it, then publish
python -m release_tool --changelog
vim changelog.txt
python -m release_tool --github-release --website

# Upload existing ISOs and generate checksums
python -m release_tool --upload --checksum

# Everything, no prompts (CI mode)
python -m release_tool --all --no-confirm --version 2026.02
```

## Changelog Workflow

Stage 5 (`--changelog`) scans all edition repos for git commits since the last tag, categorizes them (Added/Updated/Fixed/Other), and writes `changelog.txt`. This file is editable — refine it before running stages 6 and 7, which consume it for the GitHub release body and website release page entry.

## Configuration

Edit `config.yaml` to set:
- **editions** — repos and ISO name patterns to build
- **sourceforge** — upload credentials and remote path
- **github** — release repo, website repo, token env var
- **qemu** — RAM, CPUs, KVM, UEFI firmware path
- **paths** — work dir, output dir, changelog location

The GitHub token is read from the `GITHUB_TOKEN` environment variable (configurable in `config.yaml`).

## Editions

Currently configured:
- `alg-plasma` — [arch-linux-gui/alg-plasma](https://github.com/arch-linux-gui/alg-plasma)
- `alg-gnome` — [arch-linux-gui/alg-gnome](https://github.com/arch-linux-gui/alg-gnome)
- `alg-xfce` — [arch-linux-gui/alg-xfce](https://github.com/arch-linux-gui/alg-xfce)

Add or remove editions in `config.yaml`.

## License

GPLv3
