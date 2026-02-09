"""
Stage 4: Generate SHA-256 checksums for built ISOs.

Produces a sha256sum.txt file and returns a dict mapping ISO name -> checksum.
"""

from pathlib import Path

from release_tool.config import Config
from release_tool.utils import ensure_dir, log, sha256_file

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_checksums(
    config: Config,
    iso_paths: list[Path],
    dry_run: bool = False,
) -> dict[str, str]:
    """
    Compute SHA-256 checksums for all ISOs.

    Writes a sha256sum.txt file (compatible with `sha256sum -c`) in the
    output directory.

    Args:
        config:    The loaded configuration.
        iso_paths: List of ISO file paths.
        dry_run:   If True, skip actual hashing (ISOs may not exist).

    Returns:
        A dict mapping ISO filename -> SHA-256 hex digest.
    """
    log.info(f"\n=== Stage 4: Generating SHA-256 Checksums ===")

    output_dir = ensure_dir(config.paths.output_dir)
    checksums: dict[str, str] = {}

    for iso in iso_paths:
        if dry_run:
            log.info(f"  [DRY-RUN] Would compute SHA-256 for {iso.name}")
            checksums[iso.name] = "<dry-run-placeholder>"
            continue

        log.info(f"  Computing SHA-256 for {iso.name}...")
        digest = sha256_file(iso)
        checksums[iso.name] = digest
        log.info(f"    {digest}  {iso.name}")

    # Write sha256sum.txt
    if not dry_run:
        checksum_file = output_dir / "sha256sum.txt"
        with open(checksum_file, "w") as f:
            for name, digest in checksums.items():
                f.write(f"{digest}  {name}\n")
        log.info(f"\n  Checksums written to: {checksum_file}")

    log.info(f"=== Checksum generation complete. ===")

    return checksums
