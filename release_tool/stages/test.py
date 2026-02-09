"""
Stage 2: Test ISOs

Pauses the pipeline for manual ISO testing.
Optionally launches QEMU VMs for quick smoke-testing each ISO.
"""

import shutil
from pathlib import Path

from release_tool.config import Config
from release_tool.utils import confirm, find_isos, log, run_cmd

# ---------------------------------------------------------------------------
# QEMU launcher
# ---------------------------------------------------------------------------

def _launch_qemu(iso_path: Path, config: Config) -> None:
    """
    Launch a QEMU VM with the given ISO for manual testing.
    The VM is started in the foreground; the user closes it when done.
    """
    qemu_bin = "qemu-system-x86_64"
    if not shutil.which(qemu_bin):
        log.error("qemu-system-x86_64 not found. Install qemu-full to use VM testing.")
        log.error("Skipping VM launch for this ISO.")
        return

    qcfg = config.qemu
    cmd = [
        qemu_bin,
        "-cdrom", str(iso_path),
        "-m", str(qcfg.ram),
        "-smp", str(qcfg.cpus),
        "-boot", "d",
        "-display", "gtk",
        "-device", "virtio-net-pci,netdev=net0",
        "-netdev", "user,id=net0",
        "-audio", "driver=pa,model=hda",
    ]

    # KVM acceleration
    if qcfg.kvm:
        cmd.extend(["-enable-kvm", "-cpu", "host"])

    # UEFI firmware
    if qcfg.ovmf_path and Path(qcfg.ovmf_path).exists():
        cmd.extend(["-bios", qcfg.ovmf_path])
    elif qcfg.ovmf_path:
        log.warning(f"OVMF firmware not found at {qcfg.ovmf_path}, falling back to BIOS boot.")

    log.info(f"  Launching QEMU VM for {iso_path.name}...")
    log.info(f"  Close the QEMU window when testing is complete.")
    # Run in foreground — blocks until the user closes the VM
    run_cmd(cmd, check=False)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def test_isos(config: Config, iso_paths: list[Path], use_qemu: bool = False) -> bool:
    """
    Pause for manual ISO testing.

    Args:
        config:    The loaded configuration.
        iso_paths: List of ISO file paths to test.
        use_qemu:  If True, launch a QEMU VM for each ISO.

    Returns:
        True if the user confirms tests passed, False otherwise.
    """
    log.info(f"\n=== Stage 2: ISO Testing ===")

    if not iso_paths:
        log.warning("No ISO files found to test.")
        return False

    log.info(f"  ISOs to test:")
    for iso in iso_paths:
        log.info(f"    - {iso.name} ({iso.stat().st_size / (1 << 30):.2f} GiB)")

    if use_qemu:
        log.info(f"\n  QEMU testing enabled. A VM will launch for each ISO.")
        for iso in iso_paths:
            _launch_qemu(iso, config)
            log.info(f"  VM closed for {iso.name}.")
    else:
        log.info(f"\n  Manual testing mode.")
        log.info(f"  Please test the ISOs located in: {config.paths.output_dir}")
        log.info(f"  You can use any method — QEMU, VirtualBox, bare metal USB, etc.")

    print()
    passed = confirm("Have all ISOs passed testing?", default=True)

    if passed:
        log.info("  [OK] Testing passed. Proceeding to next stage.")
    else:
        log.warning("  [FAIL] Testing did not pass. Release aborted by user.")

    return passed
