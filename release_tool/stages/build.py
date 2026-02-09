"""
Stage 1: Build ISOs

Clones (or pulls) each edition repository and runs mkarchiso to produce
the ISO files.
"""

from pathlib import Path

from release_tool.config import Config, Edition
from release_tool.utils import ensure_dir, log, run_cmd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clone_or_pull(edition: Edition, work_dir: Path, dry_run: bool) -> Path:
    """
    Clone the edition repo into work_dir/<name>, or pull if it already exists.
    Returns the path to the local repo.
    """
    repo_dir = work_dir / edition.name
    if repo_dir.exists() and (repo_dir / ".git").exists():
        log.info(f"Pulling latest changes for {edition.name}...")
        run_cmd(["git", "pull", "--ff-only"], cwd=str(repo_dir), dry_run=dry_run)
    else:
        log.info(f"Cloning {edition.name} from {edition.repo}...")
        run_cmd(
            ["git", "clone", "--depth=1", edition.repo, str(repo_dir)],
            dry_run=dry_run,
        )
    return repo_dir


def _build_iso(repo_dir: Path, output_dir: Path, dry_run: bool) -> None:
    """
    Build an ISO using mkarchiso.
    Cleans previous work/out dirs inside the repo, then runs mkarchiso.
    """
    local_work = repo_dir / "work"
    local_out = repo_dir / "out"

    # Clean previous build artifacts
    if local_work.exists() or local_out.exists():
        log.info(f"  Cleaning previous build artifacts in {repo_dir.name}...")
        run_cmd(["sudo", "rm", "-rf", str(local_work), str(local_out)],
                dry_run=dry_run)

    log.info(f"  Running mkarchiso for {repo_dir.name}...")
    run_cmd(
        ["sudo", "mkarchiso", "-vvv", "-w", str(local_work), "-o", str(local_out), str(repo_dir)],
        dry_run=dry_run,
    )

    # Copy built ISO(s) to the central output directory
    if not dry_run and local_out.exists():
        for iso in local_out.glob("*.iso"):
            dest = output_dir / iso.name
            log.info(f"  Moving {iso.name} -> {output_dir}")
            run_cmd(["sudo", "mv", str(iso), str(dest)])
            # Fix ownership so the current user can handle the file
            run_cmd(["sudo", "chown", f"{_current_user()}:{_current_user()}", str(dest)])


def _current_user() -> str:
    """Return the current username."""
    import os
    return os.environ.get("USER", "root")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_all(config: Config, dry_run: bool = False) -> list[Path]:
    """
    Build ISOs for all editions defined in the config.

    Returns:
        List of paths to the built ISO files.
    """
    version = config.version
    work_dir = ensure_dir(config.paths.work_dir)
    output_dir = ensure_dir(config.paths.output_dir)

    log.info(f"=== Stage 1: Building ISOs for version {version} ===")
    log.info(f"  Editions: {', '.join(e.name for e in config.editions)}")
    log.info(f"  Work dir: {work_dir}")
    log.info(f"  Output dir: {output_dir}")

    # Check that archiso is installed
    if not dry_run:
        run_cmd(["pacman", "-Qi", "archiso"], capture=True, check=False)

    built_isos: list[Path] = []
    for edition in config.editions:
        log.info(f"\n--- Building {edition.name} ---")
        repo_dir = _clone_or_pull(edition, work_dir, dry_run)
        _build_iso(repo_dir, output_dir, dry_run)

        expected_iso = output_dir / edition.iso_filename(version)
        if dry_run:
            built_isos.append(expected_iso)
        elif expected_iso.exists():
            built_isos.append(expected_iso)
            log.info(f"  [OK] {expected_iso.name}")
        else:
            # The ISO filename may not match the expected pattern exactly
            # (mkarchiso uses date-based naming from profiledef.sh).
            # Find any new ISO in the output dir from this edition.
            for iso in output_dir.glob(f"{edition.name}*.iso"):
                built_isos.append(iso)
                log.info(f"  [OK] {iso.name}")

    log.info(f"\n=== Build complete. {len(built_isos)} ISO(s) produced. ===")
    return built_isos
