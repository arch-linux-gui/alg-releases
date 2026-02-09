"""
Configuration loader for the ALG release tool.

Reads config.yaml and provides a typed configuration object.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from release_tool.utils import current_date_version

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Edition:
    name: str
    repo: str
    iso_pattern: str

    def iso_filename(self, version: str) -> str:
        return self.iso_pattern.format(version=version)


@dataclass
class PathsConfig:
    work_dir: str = "./work"
    output_dir: str = "./out"
    changelog_file: str = "./changelog.txt"


@dataclass
class SourceForgeConfig:
    user: str = "demonkiller"
    host: str = "frs.sourceforge.net"
    remote_path: str = "/home/frs/project/arch-linux-gui/"


@dataclass
class GitHubConfig:
    releases_repo: str = "arch-linux-gui/alg-releases"
    website_repo: str = "arch-linux-gui/web"
    website_branch: str = "main"
    token_env_var: str = "GITHUB_TOKEN"


@dataclass
class QemuConfig:
    ram: int = 4096
    cpus: int = 4
    kvm: bool = True
    ovmf_path: str = "/usr/share/edk2/x64/OVMF.fd"


@dataclass
class Config:
    release_version: str = ""
    editions: list[Edition] = field(default_factory=list)
    paths: PathsConfig = field(default_factory=PathsConfig)
    sourceforge: SourceForgeConfig = field(default_factory=SourceForgeConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    qemu: QemuConfig = field(default_factory=QemuConfig)

    @property
    def version(self) -> str:
        """Return release version, falling back to YYYY.MM."""
        return self.release_version or current_date_version()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path = "config.yaml", version_override: Optional[str] = None) -> Config:
    """
    Load and validate the configuration from a YAML file.

    Args:
        config_path:      Path to the YAML configuration file.
        version_override: If provided, overrides the version in config.

    Returns:
        A populated Config instance.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    # Parse editions
    editions = []
    for ed in raw.get("editions", []):
        editions.append(Edition(
            name=ed["name"],
            repo=ed["repo"],
            iso_pattern=ed["iso_pattern"],
        ))

    # Parse paths
    paths_raw = raw.get("paths", {})
    paths = PathsConfig(
        work_dir=paths_raw.get("work_dir", "./work"),
        output_dir=paths_raw.get("output_dir", "./out"),
        changelog_file=paths_raw.get("changelog_file", "./changelog.txt"),
    )

    # Parse SourceForge
    sf_raw = raw.get("sourceforge", {})
    sourceforge = SourceForgeConfig(
        user=sf_raw.get("user", "demonkiller"),
        host=sf_raw.get("host", "frs.sourceforge.net"),
        remote_path=sf_raw.get("remote_path", "/home/frs/project/arch-linux-gui/"),
    )

    # Parse GitHub
    gh_raw = raw.get("github", {})
    github = GitHubConfig(
        releases_repo=gh_raw.get("releases_repo", "arch-linux-gui/alg-releases"),
        website_repo=gh_raw.get("website_repo", "arch-linux-gui/web"),
        website_branch=gh_raw.get("website_branch", "main"),
        token_env_var=gh_raw.get("token_env_var", "GITHUB_TOKEN"),
    )

    # Parse QEMU
    qemu_raw = raw.get("qemu", {})
    qemu = QemuConfig(
        ram=qemu_raw.get("ram", 4096),
        cpus=qemu_raw.get("cpus", 4),
        kvm=qemu_raw.get("kvm", True),
        ovmf_path=qemu_raw.get("ovmf_path", "/usr/share/edk2/x64/OVMF.fd"),
    )

    version = version_override or raw.get("release_version", "") or ""

    return Config(
        release_version=version,
        editions=editions,
        paths=paths,
        sourceforge=sourceforge,
        github=github,
        qemu=qemu,
    )
