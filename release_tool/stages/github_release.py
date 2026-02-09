"""
Stage 5: Create a GitHub Release on arch-linux-gui/alg-releases.

Uses the GitHub API (via PyGithub) to create a tagged release with
the changelog body and attach the sha256sum.txt file.
"""

import os
from pathlib import Path

from release_tool.config import Config
from release_tool.stages.changelog import load_changelog
from release_tool.utils import log

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_github_release(
    config: Config,
    checksums: dict[str, str],
    dry_run: bool = False,
) -> None:
    """
    Create a GitHub release on the releases repository.

    Args:
        config:    The loaded configuration.
        checksums: Dict mapping ISO filename -> SHA-256 digest.
        dry_run:   If True, only print what would happen.
    """
    log.info(f"\n=== Stage 5: Creating GitHub Release ===")

    version = config.version
    tag = f"v{version}"
    gh_cfg = config.github
    token_var = gh_cfg.token_env_var
    token = os.environ.get(token_var)

    if not token and not dry_run:
        log.error(f"  GitHub token not found in environment variable '{token_var}'.")
        log.error(f"  Set it with: export {token_var}=ghp_xxxx")
        return

    # Load changelog for release body
    changelog_data = load_changelog(config)
    release_body = changelog_data.get("body", "")

    # Append checksum table to the release body
    if checksums:
        release_body += "\n\n### SHA-256 Checksums\n\n"
        release_body += "| ISO | SHA-256 |\n"
        release_body += "|-----|--------|\n"
        for name, digest in checksums.items():
            release_body += f"| {name} | `{digest}` |\n"

    # Append SourceForge download links
    release_body += "\n\n### Download\n\n"
    release_body += "Download the ISOs from SourceForge:\n"
    for edition in config.editions:
        iso_name = edition.iso_filename(version)
        sf_url = f"https://sourceforge.net/projects/arch-linux-gui/files/{iso_name}/download"
        release_body += f"- **{edition.name}**: [{iso_name}]({sf_url})\n"

    if dry_run:
        log.info(f"  [DRY-RUN] Would create release '{tag}' on {gh_cfg.releases_repo}")
        log.info(f"  Release title: ALG {tag}")
        log.info(f"  --- Release Body Preview ---")
        for line in release_body.splitlines()[:30]:
            log.info(f"  | {line}")
        if len(release_body.splitlines()) > 30:
            log.info(f"  | ... ({len(release_body.splitlines()) - 30} more lines)")
        log.info(f"  --- End Preview ---")
        return

    try:
        from github import Github

        g = Github(token)
        repo = g.get_repo(gh_cfg.releases_repo)

        log.info(f"  Creating release '{tag}' on {gh_cfg.releases_repo}...")

        release = repo.create_git_release(
            tag=tag,
            name=f"ALG {tag}",
            message=release_body,
            draft=False,
            prerelease=False,
        )

        # Attach sha256sum.txt if it exists
        checksum_file = Path(config.paths.output_dir) / "sha256sum.txt"
        if checksum_file.exists():
            log.info(f"  Attaching sha256sum.txt...")
            release.upload_asset(
                str(checksum_file),
                label="SHA-256 Checksums",
                content_type="text/plain",
            )

        log.info(f"  [OK] Release created: {release.html_url}")

    except ImportError:
        log.error("  PyGithub is not installed. Run: pip install PyGithub")
    except Exception as e:
        log.error(f"  Failed to create GitHub release: {e}")

    log.info(f"=== GitHub Release stage complete. ===")
