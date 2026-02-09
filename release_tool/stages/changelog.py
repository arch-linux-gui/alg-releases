"""
Changelog generator.

Reads git commits from all edition repositories (and the releases repo itself)
since the last release tag, and produces an editable changelog.txt.

The user can then review/edit the file before it is used for the GitHub
release body and the website release page.
"""

import re
from datetime import date
from pathlib import Path
from typing import Optional

from release_tool.config import Config, Edition
from release_tool.utils import ensure_dir, log, run_cmd_output

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_latest_tag(repo_dir: str) -> Optional[str]:
    """
    Get the most recent tag in a repo.
    Returns None if no tags exist.
    """
    try:
        tag = run_cmd_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_dir,
        )
        return tag if tag else None
    except Exception:
        return None


def _get_commits_since_tag(repo_dir: str, tag: Optional[str]) -> list[str]:
    """
    Get one-line commit messages since a given tag.
    If tag is None, gets ALL commits (for first release).
    """
    if tag:
        cmd = ["git", "log", f"{tag}..HEAD", "--oneline", "--no-merges"]
    else:
        cmd = ["git", "log", "--oneline", "--no-merges", "-50"]

    try:
        output = run_cmd_output(cmd, cwd=repo_dir)
        if not output:
            return []
        return output.splitlines()
    except Exception:
        return []


def _categorize_commits(commits: list[str]) -> dict[str, list[str]]:
    """
    Attempt to categorize commits into Added/Updated/Fixed/Other
    based on common commit message patterns.
    """
    categories: dict[str, list[str]] = {
        "Added": [],
        "Updated": [],
        "Fixed": [],
        "Other": [],
    }

    # Patterns (case-insensitive)
    add_pattern = re.compile(r"^[a-f0-9]+\s+(add|new|feat|introduce|create|implement)", re.IGNORECASE)
    update_pattern = re.compile(r"^[a-f0-9]+\s+(update|upgrade|bump|upd|improve|enhance|refactor)", re.IGNORECASE)
    fix_pattern = re.compile(r"^[a-f0-9]+\s+(fix|bugfix|hotfix|patch|resolve|correct)", re.IGNORECASE)

    for commit in commits:
        # Strip the commit hash prefix for the message
        parts = commit.split(" ", 1)
        if len(parts) < 2:
            continue
        msg = parts[1].strip()
        if not msg:
            continue

        if add_pattern.match(commit):
            categories["Added"].append(msg)
        elif update_pattern.match(commit):
            categories["Updated"].append(msg)
        elif fix_pattern.match(commit):
            categories["Fixed"].append(msg)
        else:
            categories["Other"].append(msg)

    return categories


def _format_changelog(
    version: str,
    all_changes: dict[str, dict[str, list[str]]],
) -> str:
    """
    Format the changelog as a human-readable (and editable) text file.
    """
    today = date.today().strftime("%B %d, %Y")
    lines = [
        f"ALG Release v{version}",
        f"Date: {today}",
        "=" * 60,
        "",
        "RELEASE NOTES",
        "-" * 40,
        "",
        "Summary:",
        "(Write a brief summary of this release here)",
        "",
    ]

    for repo_name, categories in all_changes.items():
        has_changes = any(v for v in categories.values())
        if not has_changes:
            continue

        lines.append(f"[{repo_name}]")
        lines.append("-" * 40)

        for category in ["Added", "Updated", "Fixed", "Other"]:
            items = categories.get(category, [])
            if items:
                lines.append(f"  {category}:")
                for item in items:
                    lines.append(f"    - {item}")
                lines.append("")

        lines.append("")

    lines.extend([
        "=" * 60,
        "INSTRUCTIONS:",
        "- Edit this file to refine the release notes before publishing.",
        "- The section above 'INSTRUCTIONS' will be used as the GitHub",
        "  release body and mirrored on the website.",
        "- Lines starting with '#' are comments and will be stripped.",
        "- Delete or add entries as you see fit.",
        "- When done, save the file and continue the release process.",
        "=" * 60,
    ])

    return "\n".join(lines) + "\n"


def _parse_changelog_for_release(changelog_path: Path) -> dict:
    """
    Parse a changelog.txt file back into structured data for the GitHub
    release and website.

    Returns:
        {
            "summary": str,
            "body": str,          # Full markdown body for GH release
            "highlights": [str],
            "changes": {"added": [], "updated": [], "fixed": [], "removed": []},
        }
    """
    if not changelog_path.exists():
        return {"summary": "", "body": "", "highlights": [], "changes": {}}

    content = changelog_path.read_text()

    # Strip everything after INSTRUCTIONS marker
    instructions_marker = "=" * 60 + "\nINSTRUCTIONS:"
    if instructions_marker in content:
        content = content[:content.index(instructions_marker)].strip()

    # Strip comment lines
    lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
    body = "\n".join(lines)

    # Extract summary (text between "Summary:" and the first "[repo]" section)
    summary = ""
    summary_match = re.search(r"Summary:\s*\n(.*?)(?=\n\[|\n={4,}|\Z)", body, re.DOTALL)
    if summary_match:
        summary = summary_match.group(1).strip()
        if summary == "(Write a brief summary of this release here)":
            summary = ""

    # Extract categorized items across all repos
    changes: dict[str, list[str]] = {"added": [], "updated": [], "fixed": [], "removed": []}
    highlights: list[str] = []

    for category_label, key in [("Added", "added"), ("Updated", "updated"), ("Fixed", "fixed"), ("Removed", "removed")]:
        pattern = rf"{category_label}:\s*\n((?:\s+-\s+.+\n?)*)"
        for match in re.finditer(pattern, body):
            items_block = match.group(1)
            for item_match in re.finditer(r"-\s+(.+)", items_block):
                changes[key].append(item_match.group(1).strip())

    # Use a mix of Added and Updated as highlights
    for item in (changes["added"][:3] + changes["updated"][:2] + changes["fixed"][:2]):
        highlights.append(item)

    # Build a markdown body for the GitHub release
    md_lines = []
    if summary:
        md_lines.append(summary)
        md_lines.append("")

    for label, key in [("### Added", "added"), ("### Updated", "updated"), ("### Fixed", "fixed"), ("### Removed", "removed")]:
        if changes[key]:
            md_lines.append(label)
            for item in changes[key]:
                md_lines.append(f"- {item}")
            md_lines.append("")

    md_body = "\n".join(md_lines).strip()

    return {
        "summary": summary,
        "body": md_body if md_body else body,
        "highlights": highlights,
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_changelog(config: Config) -> Path:
    """
    Scan all edition repos (and the releases repo) for commits since the
    last tag, then write an editable changelog.txt.

    Returns:
        Path to the generated changelog file.
    """
    log.info(f"\n=== Generating Changelog for v{config.version} ===")

    work_dir = Path(config.paths.work_dir)
    all_changes: dict[str, dict[str, list[str]]] = {}

    # Scan each edition repo
    for edition in config.editions:
        repo_dir = work_dir / edition.name
        if not repo_dir.exists():
            log.warning(f"  Repo dir not found for {edition.name}, skipping commit scan.")
            continue

        log.info(f"  Scanning {edition.name} for commits...")
        latest_tag = _get_latest_tag(str(repo_dir))
        if latest_tag:
            log.info(f"    Last tag: {latest_tag}")
        else:
            log.info(f"    No previous tags found, scanning recent commits.")

        commits = _get_commits_since_tag(str(repo_dir), latest_tag)
        log.info(f"    Found {len(commits)} commit(s) since last release.")

        categories = _categorize_commits(commits)
        all_changes[edition.name] = categories

    # Also scan the releases repo itself (current directory)
    log.info(f"  Scanning alg-releases for commits...")
    releases_tag = _get_latest_tag(".")
    releases_commits = _get_commits_since_tag(".", releases_tag)
    if releases_commits:
        all_changes["alg-releases"] = _categorize_commits(releases_commits)

    # Write changelog
    changelog_path = Path(config.paths.changelog_file)
    changelog_content = _format_changelog(config.version, all_changes)
    changelog_path.write_text(changelog_content)

    log.info(f"\n  Changelog written to: {changelog_path}")
    log.info(f"  Please review and edit the changelog before proceeding.")
    log.info(f"=== Changelog generation complete. ===")

    return changelog_path


def load_changelog(config: Config) -> dict:
    """
    Load and parse an existing changelog.txt for use in the GitHub release
    and website update stages.

    Returns:
        Parsed changelog data dict.
    """
    changelog_path = Path(config.paths.changelog_file)
    if not changelog_path.exists():
        log.warning(f"Changelog not found at {changelog_path}")
        return {"summary": "", "body": "", "highlights": [], "changes": {}}

    return _parse_changelog_for_release(changelog_path)
