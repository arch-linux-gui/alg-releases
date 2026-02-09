"""
Shared utility functions for the ALG release tool.
"""

import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "[%(levelname)s] %(message)s"

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the root logger."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, level=level, stream=sys.stderr)
    return logging.getLogger("alg-release")


log = logging.getLogger("alg-release")

# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: list[str],
    cwd: Optional[str] = None,
    dry_run: bool = False,
    capture: bool = False,
    check: bool = True,
) -> Optional[subprocess.CompletedProcess]:
    """
    Run a shell command with logging.

    Args:
        cmd:      Command as a list of strings.
        cwd:      Working directory.
        dry_run:  If True, only log the command without executing.
        capture:  Capture stdout/stderr instead of streaming to console.
        check:    Raise on non-zero exit code.

    Returns:
        CompletedProcess if executed, None if dry_run.
    """
    cmd_str = " ".join(cmd)
    if dry_run:
        log.info(f"[DRY-RUN] {cmd_str}")
        return None

    log.debug(f"Running: {cmd_str}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=check,
    )
    return result


def run_cmd_output(cmd: list[str], cwd: Optional[str] = None) -> str:
    """Run a command and return its stdout, stripped."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_file(filepath: str | Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):  # 1 MiB chunks
            h.update(chunk)
    return h.hexdigest()

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str | Path) -> Path:
    """Create directory (and parents) if it doesn't exist, return Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_isos(directory: str | Path) -> list[Path]:
    """Return a sorted list of .iso files in *directory*."""
    d = Path(directory)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.iso"))

# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------

def confirm(prompt: str, default: bool = False) -> bool:
    """Ask the user a yes/no question. Returns True for yes."""
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")

# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def current_date_version() -> str:
    """Return a version string like '2026.02' based on today's date."""
    from datetime import date
    today = date.today()
    return f"{today.year}.{today.month:02d}"
