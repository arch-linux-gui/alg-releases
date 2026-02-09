#!/usr/bin/env python3
"""
ALG Release Tool — CLI entry point.

Usage:
    python -m release_tool --help
    python -m release_tool --all
    python -m release_tool --build --checksum
    python -m release_tool --upload --github-release --website
"""

import argparse
import sys
from pathlib import Path

from release_tool.config import load_config
from release_tool.utils import confirm, find_isos, log, setup_logging


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="alg-release",
        description="ALG (Arka Linux GUI) Release Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Stage overview:
  1. --build            Clone/pull repos and build ISOs with mkarchiso
  2. --test             Pause for manual ISO testing (add --qemu for VMs)
  3. --upload           Upload ISOs to SourceForge via rsync
  4. --checksum         Generate SHA-256 checksums for all ISOs
  5. --changelog        Auto-generate changelog from git commits
  6. --github-release   Create a tagged release on GitHub
  7. --website          Update the ALG website repo (Isodata.ts + ReleasePage.tsx)
  
  --all                Run all stages sequentially (1 → 7)

Examples:
  # Full release pipeline
  alg-release --all --version 2026.02

  # Build only
  alg-release --build

  # Test with QEMU VMs
  alg-release --test --qemu

  # Generate changelog, edit it, then publish
  alg-release --changelog
  # ... edit changelog.txt ...
  alg-release --github-release --website

  # Dry run everything
  alg-release --all --dry-run
""",
    )

    # Stage flags
    stages = p.add_argument_group("Stages")
    stages.add_argument("--all", action="store_true",
                        help="Run all stages sequentially")
    stages.add_argument("--build", action="store_true",
                        help="Stage 1: Build ISOs")
    stages.add_argument("--test", action="store_true",
                        help="Stage 2: Manual ISO testing")
    stages.add_argument("--upload", action="store_true",
                        help="Stage 3: Upload ISOs to SourceForge")
    stages.add_argument("--checksum", action="store_true",
                        help="Stage 4: Generate SHA-256 checksums")
    stages.add_argument("--changelog", action="store_true",
                        help="Stage 5: Auto-generate changelog from git commits")
    stages.add_argument("--github-release", action="store_true",
                        help="Stage 6: Create GitHub release")
    stages.add_argument("--website", action="store_true",
                        help="Stage 7: Update ALG website")

    # Options
    opts = p.add_argument_group("Options")
    opts.add_argument("--version", type=str, default=None,
                      help="Release version override (default: YYYY.MM from date)")
    opts.add_argument("--config", type=str, default="config.yaml",
                      help="Path to config.yaml (default: ./config.yaml)")
    opts.add_argument("--dry-run", action="store_true",
                      help="Print commands without executing destructive operations")
    opts.add_argument("--qemu", action="store_true",
                      help="Launch QEMU VMs for ISO testing (used with --test)")
    opts.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose/debug logging")
    opts.add_argument("--no-confirm", action="store_true",
                      help="Skip confirmation prompts (for CI/scripted use)")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(verbose=args.verbose)

    # If no stage flags at all, show help
    stage_flags = [
        args.all, args.build, args.test, args.upload,
        args.checksum, args.changelog, args.github_release, args.website,
    ]
    if not any(stage_flags):
        log.error("No stage specified. Use --all or individual stage flags.")
        log.error("Run with --help for usage information.")
        return 1

    # Load configuration
    try:
        config = load_config(args.config, version_override=args.version)
    except FileNotFoundError as e:
        log.error(str(e))
        return 1

    version = config.version
    log.info(f"ALG Release Tool — Version: v{version}")
    log.info(f"Editions: {', '.join(e.name for e in config.editions)}")
    log.info(f"Dry run: {args.dry_run}")
    print()

    # Determine which stages to run
    run_build = args.all or args.build
    run_test = args.all or args.test
    run_upload = args.all or args.upload
    run_checksum = args.all or args.checksum
    run_changelog = args.all or args.changelog
    run_gh_release = args.all or args.github_release
    run_website = args.all or args.website

    iso_paths: list[Path] = []
    checksums: dict[str, str] = {}

    # -----------------------------------------------------------------------
    # Stage 1: Build ISOs
    # -----------------------------------------------------------------------
    if run_build:
        from release_tool.stages.build import build_all
        iso_paths = build_all(config, dry_run=args.dry_run)
        if not iso_paths and not args.dry_run:
            log.error("Build produced no ISOs. Aborting.")
            return 1

    # Discover existing ISOs if we skipped the build stage
    if not iso_paths:
        iso_paths = find_isos(config.paths.output_dir)
        if iso_paths:
            log.info(f"Found {len(iso_paths)} existing ISO(s) in {config.paths.output_dir}:")
            for iso in iso_paths:
                log.info(f"  - {iso.name}")

    # -----------------------------------------------------------------------
    # Stage 2: Test ISOs
    # -----------------------------------------------------------------------
    if run_test:
        from release_tool.stages.test import test_isos
        if not iso_paths and not args.dry_run:
            log.error("No ISOs found for testing.")
            return 1

        passed = test_isos(config, iso_paths, use_qemu=args.qemu)
        if not passed and not args.no_confirm:
            log.error("Testing did not pass. Aborting release.")
            return 1

    # -----------------------------------------------------------------------
    # Stage 3: Upload to SourceForge
    # -----------------------------------------------------------------------
    if run_upload:
        from release_tool.stages.upload import upload_isos
        if not iso_paths and not args.dry_run:
            log.error("No ISOs found to upload.")
            return 1
        upload_isos(config, iso_paths, dry_run=args.dry_run)

    # -----------------------------------------------------------------------
    # Stage 4: Generate Checksums
    # -----------------------------------------------------------------------
    if run_checksum:
        from release_tool.stages.checksum import generate_checksums
        if not iso_paths and not args.dry_run:
            log.error("No ISOs found for checksum generation.")
            return 1
        checksums = generate_checksums(config, iso_paths, dry_run=args.dry_run)

    # Load checksums from file if we skipped the checksum stage
    if not checksums:
        checksum_file = Path(config.paths.output_dir) / "sha256sum.txt"
        if checksum_file.exists():
            log.info(f"Loading existing checksums from {checksum_file}")
            for line in checksum_file.read_text().splitlines():
                parts = line.strip().split("  ", 1)
                if len(parts) == 2:
                    checksums[parts[1]] = parts[0]

    # -----------------------------------------------------------------------
    # Stage 5: Generate Changelog
    # -----------------------------------------------------------------------
    if run_changelog:
        from release_tool.stages.changelog import generate_changelog
        changelog_path = generate_changelog(config)

        # In --all mode, pause for user to edit the changelog
        if args.all and not args.no_confirm:
            print()
            log.info(f"Changelog written to: {changelog_path}")
            log.info("Please review and edit the changelog file now.")
            log.info("The contents will be used for the GitHub release and website.")
            input("\nPress Enter when you're done editing the changelog... ")

    # -----------------------------------------------------------------------
    # Stage 6: GitHub Release
    # -----------------------------------------------------------------------
    if run_gh_release:
        from release_tool.stages.github_release import create_github_release
        create_github_release(config, checksums, dry_run=args.dry_run)

    # -----------------------------------------------------------------------
    # Stage 7: Update Website
    # -----------------------------------------------------------------------
    if run_website:
        from release_tool.stages.website_update import update_website
        update_website(config, checksums, dry_run=args.dry_run)

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    print()
    log.info("=" * 60)
    log.info(f"ALG v{version} release process complete!")
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
