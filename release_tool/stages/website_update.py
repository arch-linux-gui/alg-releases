"""
Stage 6: Update the ALG website repository.

Updates two files in the arch-linux-gui/web repo:
  1. lib/Isodata.ts    - Download links and SHA-256 checksums
  2. app/releases/ReleasePage.tsx - Release history entry

Creates a branch and opens a Pull Request against the website repo.
"""

import os
import re
from datetime import date
from pathlib import Path
from textwrap import indent

from release_tool.config import Config
from release_tool.stages.changelog import load_changelog
from release_tool.utils import log

# ---------------------------------------------------------------------------
# Helpers for generating file contents
# ---------------------------------------------------------------------------

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _generate_isodata_ts(config: Config, checksums: dict[str, str]) -> str:
    """
    Generate the full contents of lib/Isodata.ts with updated links
    and SHA-256 checksums.
    """
    version = config.version
    today = date.today()
    month_name = _MONTH_NAMES[today.month]
    release_date = f"{month_name} {today.year}"

    def _sf_url(edition_name: str) -> str:
        for ed in config.editions:
            if ed.name == edition_name:
                iso = ed.iso_filename(version)
                return f"https://sourceforge.net/projects/arch-linux-gui/files/{iso}/download"
        return ""

    def _checksum(edition_name: str) -> str:
        for ed in config.editions:
            if ed.name == edition_name:
                iso = ed.iso_filename(version)
                return checksums.get(iso, "")
        return ""

    return f'''interface IsoLinks {{
    sourceforge: string;
    checksum: string;
}}

interface IsoData {{
    kde: IsoLinks;
    gnome: IsoLinks;
    xfce: IsoLinks;
}}

interface ReleaseData {{
    releaseVer: string;
    releaseDate: string
}}

export const releaseData: ReleaseData = {{
    releaseVer: "v{version}",
    releaseDate: "{release_date}"
}}

export const themedIso: IsoData = {{
    kde: {{
        sourceforge:
            "{_sf_url("alg-plasma")}",
        checksum:
            "{_checksum("alg-plasma")}",
    }},
    gnome: {{
        sourceforge:
            "{_sf_url("alg-gnome")}",
        checksum:
            "{_checksum("alg-gnome")}",
    }},
    xfce: {{
        sourceforge:
            "{_sf_url("alg-xfce")}",
        checksum:
            "{_checksum("alg-xfce")}",
    }},
}};
'''


def _generate_new_release_entry(config: Config, checksums: dict[str, str]) -> str:
    """
    Generate a TypeScript object literal for a new release entry
    to prepend to the releases array in ReleasePage.tsx.
    """
    version = config.version
    today = date.today()
    month_name = _MONTH_NAMES[today.month]
    release_date = f"{month_name} {today.year}"

    changelog_data = load_changelog(config)
    changes = changelog_data.get("changes", {})
    highlights = changelog_data.get("highlights", [])

    # Fallback highlights if none from changelog
    if not highlights:
        highlights = [
            "Updated to latest kernel and software packages",
            "Improved hardware compatibility",
            "Performance optimizations across all editions",
        ]

    def _ts_array(items: list[str], indent_level: int = 6) -> str:
        if not items:
            return "[]"
        pad = " " * indent_level
        entries = ",\n".join(f'{pad}"{item}"' for item in items)
        return f"[\n{entries},\n{" " * (indent_level - 2)}]"

    def _sf_url(edition_name: str) -> str:
        for ed in config.editions:
            if ed.name == edition_name:
                iso = ed.iso_filename(version)
                return f"https://sourceforge.net/projects/arch-linux-gui/files/{iso}/download"
        return ""

    added = changes.get("added", [])
    updated = changes.get("updated", [])
    fixed = changes.get("fixed", [])
    removed = changes.get("removed", [])

    entry = f"""  {{
    version: "{version}",
    date: "{release_date}",
    type: "major",
    isLatest: true,
    highlights: {_ts_array(highlights, 6)},
    changes: {{
      added: {_ts_array(added, 8) if added else "[]"},
      updated: {_ts_array(updated, 8) if updated else "[]"},
      fixed: {_ts_array(fixed, 8) if fixed else "[]"},
      removed: {_ts_array(removed, 8) if removed else "[]"},
    }},
    downloads: {{
      kde: "{_sf_url("alg-plasma")}",
      gnome: "{_sf_url("alg-gnome")}",
      xfce: "{_sf_url("alg-xfce")}",
    }},
  }}"""

    return entry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_website(
    config: Config,
    checksums: dict[str, str],
    dry_run: bool = False,
) -> None:
    """
    Update the ALG website repository with new release data.

    Creates a branch, updates Isodata.ts and ReleasePage.tsx, commits,
    pushes, and opens a PR.

    Args:
        config:    The loaded configuration.
        checksums: Dict mapping ISO filename -> SHA-256 digest.
        dry_run:   If True, generate the files locally but don't push/PR.
    """
    log.info(f"\n=== Stage 6: Updating Website ===")

    version = config.version
    gh_cfg = config.github
    token_var = gh_cfg.token_env_var
    token = os.environ.get(token_var)

    if not token and not dry_run:
        log.error(f"  GitHub token not found. Set {token_var} env var.")
        return

    # Generate file contents
    isodata_content = _generate_isodata_ts(config, checksums)
    new_release_entry = _generate_new_release_entry(config, checksums)

    if dry_run:
        log.info(f"  [DRY-RUN] Would update website repo {gh_cfg.website_repo}")
        log.info(f"\n  --- lib/Isodata.ts Preview ---")
        for line in isodata_content.splitlines()[:20]:
            log.info(f"  | {line}")
        log.info(f"  --- End Preview ---")
        log.info(f"\n  --- New ReleasePage entry Preview ---")
        for line in new_release_entry.splitlines()[:20]:
            log.info(f"  | {line}")
        log.info(f"  --- End Preview ---")

        # Write previews locally for inspection
        preview_dir = Path(config.paths.output_dir) / "website_preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        (preview_dir / "Isodata.ts").write_text(isodata_content)
        (preview_dir / "new_release_entry.txt").write_text(new_release_entry)
        log.info(f"\n  Preview files written to {preview_dir}/")
        return

    try:
        from github import Github, GithubException

        g = Github(token)
        repo = g.get_repo(gh_cfg.website_repo)
        branch_name = f"release/v{version}"

        # Get the default branch SHA
        default_branch = repo.get_branch(gh_cfg.website_branch)
        sha = default_branch.commit.sha

        # Create a new branch
        log.info(f"  Creating branch '{branch_name}' on {gh_cfg.website_repo}...")
        try:
            repo.create_git_ref(f"refs/heads/{branch_name}", sha)
        except GithubException as e:
            if e.status == 422:  # Branch already exists
                log.warning(f"  Branch '{branch_name}' already exists. Updating it.")
            else:
                raise

        # Update lib/Isodata.ts
        log.info(f"  Updating lib/Isodata.ts...")
        _update_file_on_github(
            repo, "lib/Isodata.ts", isodata_content,
            f"release: update Isodata.ts for v{version}",
            branch_name,
        )

        # Update app/releases/ReleasePage.tsx
        log.info(f"  Updating app/releases/ReleasePage.tsx...")
        _update_release_page(
            repo, new_release_entry, version, branch_name,
        )

        # Create Pull Request
        log.info(f"  Creating Pull Request...")
        changelog_data = load_changelog(config)
        pr_body = f"## ALG Release v{version}\n\n"
        pr_body += "This PR updates the website with the new release data.\n\n"
        pr_body += "### Changes\n"
        pr_body += "- Updated `lib/Isodata.ts` with new ISO links and SHA-256 checksums\n"
        pr_body += "- Added v{version} entry to `app/releases/ReleasePage.tsx`\n"

        pr = repo.create_pull(
            title=f"Release v{version}: Update website",
            body=pr_body,
            head=branch_name,
            base=gh_cfg.website_branch,
        )
        log.info(f"  [OK] Pull Request created: {pr.html_url}")

    except ImportError:
        log.error("  PyGithub is not installed. Run: pip install PyGithub")
    except Exception as e:
        log.error(f"  Failed to update website: {e}")

    log.info(f"=== Website update stage complete. ===")


def _update_file_on_github(repo, file_path: str, content: str, message: str, branch: str) -> None:
    """Update (or create) a file on GitHub via the API."""
    try:
        existing = repo.get_contents(file_path, ref=branch)
        repo.update_file(
            file_path, message, content, existing.sha, branch=branch,
        )
    except Exception:
        # File doesn't exist yet
        repo.create_file(file_path, message, content, branch=branch)


def _update_release_page(repo, new_entry: str, version: str, branch: str) -> None:
    """
    Update ReleasePage.tsx by:
    1. Setting isLatest: false on any existing latest entries
    2. Prepending the new release entry to the releases array
    """
    file_path = "app/releases/ReleasePage.tsx"
    try:
        existing = repo.get_contents(file_path, ref=branch)
        content = existing.decoded_content.decode("utf-8")

        # Remove isLatest: true from previous entries
        content = content.replace("isLatest: true,", "isLatest: false,")

        # Find the releases array and insert the new entry at the top
        # Pattern: const releases: Release[] = [
        marker = "const releases: Release[] = ["
        if marker in content:
            insert_pos = content.index(marker) + len(marker)
            content = content[:insert_pos] + "\n" + new_entry + "," + content[insert_pos:]
        else:
            log.warning("  Could not find releases array marker in ReleasePage.tsx")
            log.warning("  The new entry will need to be added manually.")

        repo.update_file(
            file_path,
            f"release: add v{version} to release page",
            content,
            existing.sha,
            branch=branch,
        )
    except Exception as e:
        log.error(f"  Failed to update {file_path}: {e}")
