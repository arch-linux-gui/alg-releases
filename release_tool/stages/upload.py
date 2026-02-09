"""
Stage 3: Upload ISOs to SourceForge via rsync+ssh.
"""

from pathlib import Path

from release_tool.config import Config
from release_tool.utils import log, run_cmd

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_isos(config: Config, iso_paths: list[Path], dry_run: bool = False) -> None:
    """
    Upload each ISO to SourceForge using rsync over SSH.

    Args:
        config:    The loaded configuration.
        iso_paths: List of ISO files to upload.
        dry_run:   If True, only print the commands without executing.
    """
    sf = config.sourceforge
    remote = f"{sf.user}@{sf.host}:{sf.remote_path}"

    log.info(f"\n=== Stage 3: Uploading ISOs to SourceForge ===")
    log.info(f"  Remote destination: {remote}")

    if not iso_paths:
        log.warning("  No ISOs to upload.")
        return

    for i, iso in enumerate(iso_paths, 1):
        log.info(f"\n  [{i}/{len(iso_paths)}] Uploading {iso.name}...")
        cmd = [
            "rsync", "-avP",
            "-e", "ssh",
            str(iso),
            remote,
        ]
        run_cmd(cmd, dry_run=dry_run)
        log.info(f"  [OK] {iso.name} uploaded.")

    log.info(f"\n=== Upload complete. {len(iso_paths)} ISO(s) uploaded. ===")
