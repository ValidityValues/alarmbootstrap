"""Arch-native CLI with a compatibility route to the imported pmbootstrap code."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .catalog import BUILTIN_CATALOG, load_catalog, merge_catalogs, sync_nura_catalog
from .pixel4 import (
    Pixel4Error,
    inspect_rootfs,
    run_uboot_build,
    stage_kernel,
    unpack_nura_packages,
)
from .rootfs import DEFAULT_AARCH64_URL, RootfsError, install_rootfs, root_command

NATIVE_ACTIONS = {"init", "devices", "install", "status", "chroot", "export", "pixel4"}


def default_workdir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "alarmbootstrap"


def default_config() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "alarmbootstrap/config.json"


def _read_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Configuration not found: {path}. Run alarmbootstrap init first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("workdir"), str):
        raise RuntimeError(f"Invalid configuration file: {path}")
    return data


def _workdir(args: argparse.Namespace) -> Path:
    config_path = args.config
    configured = _read_config(config_path).get("workdir") if config_path.is_file() else None
    return Path(args.workdir or configured or default_workdir()).expanduser().resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alarmbootstrap",
        description="Bootstrap Arch Linux ARM root filesystems and device boot artifacts.",
    )
    parser.add_argument("--version", action="version", version=f"alarmbootstrap {__version__}")
    parser.add_argument(
        "--config", type=Path, default=default_config(),
        help="configuration file (default: ~/.config/alarmbootstrap/config.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show additional progress")
    subs = parser.add_subparsers(dest="action")

    init = subs.add_parser("init", help="create or update alarmbootstrap configuration")
    init.add_argument("--device", default="google-flame", help="device ID (currently google-flame)")
    init.add_argument("--workdir", type=Path, default=None, help="working directory")

    devices = subs.add_parser("devices", help="list devices or sync the Nura catalog")
    devices.add_argument("--query", default="", help="filter by device ID or name")
    devices.add_argument("--sync-nura", action="store_true", help="import pmaports deviceinfo records")
    devices.add_argument("--ports-dir", type=Path, default=None, help="existing pmaports checkout")
    devices.add_argument("--output", type=Path, default=None, help="catalog JSON output path")
    devices.add_argument("--workdir", type=Path, default=None)

    install = subs.add_parser("install", help="download and extract Arch Linux ARM AArch64 rootfs")
    install.add_argument("--url", default=DEFAULT_AARCH64_URL, help="generic AArch64 rootfs URL")
    install.add_argument("--force", action="store_true", help="replace only the local rootfs directory")
    install.add_argument("--workdir", type=Path, default=None)

    status = subs.add_parser("status", help="show profile and local rootfs status")
    status.add_argument("--workdir", type=Path, default=None)

    chroot = subs.add_parser("chroot", help="enter the staged AArch64 rootfs")
    chroot.add_argument("command", nargs=argparse.REMAINDER, help="optional command inside rootfs")
    chroot.add_argument("--workdir", type=Path, default=None)

    export = subs.add_parser("export", help="export rootfs as a compressed tar archive")
    export.add_argument("--destination", type=Path, default=None, help="output archive path")
    export.add_argument("--workdir", type=Path, default=None)

    pixel4 = subs.add_parser("pixel4", help="Google Pixel 4 (google-flame) utilities")
    pixel_sub = pixel4.add_subparsers(dest="pixel_action", required=True)
    stage = pixel_sub.add_parser("stage-kernel", help="reuse the existing Nura SM8150 kernel stack")
    stage_source = stage.add_mutually_exclusive_group(required=True)
    stage_source.add_argument("--nura-rootfs", type=Path, help="existing Nura rootfs directory")
    stage_source.add_argument(
        "--package", dest="nura_packages", type=Path, action="append",
        help="Nura .apk artifact to extract (repeat for kernel and firmware packages)",
    )
    stage.add_argument("--workdir", type=Path, default=None)
    inspect = pixel_sub.add_parser("inspect", help="check staged Pixel 4 artifacts")
    inspect.add_argument("--workdir", type=Path, default=None)
    uboot = pixel_sub.add_parser("build-uboot", help="build Andrew Gigena's Pixel 4 U-Boot branch")
    uboot.add_argument("--flash", action="store_true", help="flash boot only after an explicit prompt")
    uboot.add_argument("--source", type=Path, default=None, help="reuse a clean source checkout")
    uboot.add_argument("--workdir", type=Path, default=None)
    return parser


def _legacy(argv: Sequence[str]) -> int:
    """Dispatch to the unmodified upstream command implementations where possible."""
    import pmb

    previous_argv = sys.argv[:]
    sys.argv = [previous_argv[0], *argv]
    try:
        return pmb.main()
    finally:
        sys.argv = previous_argv


def _command_index(argv: list[str]) -> int | None:
    """Find the first command token while skipping known global options."""
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"-v", "--verbose", "--version"}:
            index += 1
            continue
        if token == "--config":
            index += 2
            continue
        if token.startswith("--config="):
            index += 1
            continue
        if token.startswith("-"):
            return None
        return index
    return None


def _device_catalog(workdir: Path) -> dict[str, Any]:
    builtin = load_catalog(BUILTIN_CATALOG)
    extra = workdir / "device-catalog.json"
    if not extra.is_file():
        return builtin
    synced = load_catalog(extra)
    return merge_catalogs(builtin, {item["id"]: item for item in synced["devices"]})


def _run_chroot(rootfs: Path, requested: list[str]) -> int:
    if platform.machine().lower() not in {"aarch64", "arm64"}:
        handler = Path("/proc/sys/fs/binfmt_misc/qemu-aarch64")
        if not handler.exists():
            raise RuntimeError(
                "Cross-architecture chroot requires a registered qemu-aarch64 binfmt handler. "
                "Configure host QEMU/binfmt first; alarmbootstrap will not change host binfmt."
            )

    command = requested or ["/bin/bash"]
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        command = ["/bin/bash"]

    bind_sources = ["/dev", "/proc", "/sys"]
    mounted: list[Path] = []
    try:
        for source in bind_sources:
            target = rootfs / source.lstrip("/")
            subprocess.run(root_command(["mkdir", "-p", str(target)]), check=True)
            subprocess.run(root_command(["mount", "--rbind", source, str(target)]), check=True)
            mounted.append(target)
        return subprocess.run(root_command(["chroot", str(rootfs), *command]), check=False).returncode
    finally:
        for target in reversed(mounted):
            subprocess.run(root_command(["umount", "-R", str(target)]), check=False)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _parser().print_help()
        return 0
    if argv[0] == "legacy":
        return _legacy(argv[1:])
    if argv[0] in {"-h", "--help", "--version"}:
        try:
            _parser().parse_args(argv)
        except SystemExit as exc:
            return int(exc.code or 0)
        return 0

    index = _command_index(argv)
    if index is None or argv[index] not in NATIVE_ACTIONS:
        return _legacy(argv)

    try:
        args = _parser().parse_args(argv)
        if args.action == "init":
            if args.device != "google-flame":
                raise RuntimeError(
                    "Arch-native installation currently targets google-flame. Other Nura IDs "
                    "remain catalogued but do not yet have native Arch profiles."
                )
            workdir = Path(args.workdir or default_workdir()).expanduser().resolve()
            workdir.mkdir(parents=True, exist_ok=True)
            args.config.parent.mkdir(parents=True, exist_ok=True)
            config = {"schema_version": 1, "device": args.device, "workdir": str(workdir)}
            args.config.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            print(f"Configuration written to {args.config}")
            print(f"Device: {args.device}\nWork directory: {workdir}")
            return 0

        workdir = _workdir(args)

        if args.action == "devices":
            if args.sync_nura:
                output = args.output or (workdir / "device-catalog.json")
                result = sync_nura_catalog(output, args.ports_dir, BUILTIN_CATALOG)
                retired = sum(not item.get("upstream_present", True) for item in result["devices"])
                print(f"Saved {len(result['devices'])} device records to {output}")
                print(f"Preserved retired records: {retired}")
                return 0
            catalog = _device_catalog(workdir)
            query = args.query.casefold()
            records = [
                item for item in catalog["devices"]
                if query in str(item.get("id", "")).casefold()
                or query in str(item.get("name", "")).casefold()
            ]
            for item in records:
                status_text = "upstream" if item.get("upstream_present", True) else "preserved/retired"
                marker = " (Arch-native priority)" if item.get("id") == "google-flame" else ""
                print(f"{item['id']:<32} {item.get('name', item['id'])}{marker} [{status_text}]")
            print(f"{len(records)} record(s)")
            return 0

        if args.action == "install":
            config = _read_config(args.config)
            if config.get("device") != "google-flame":
                raise RuntimeError("This Arch-native installer currently targets google-flame.")
            rootfs = install_rootfs(workdir, args.url, args.force)
            print(f"Arch Linux ARM rootfs extracted to: {rootfs}")
            print("No device partitions were changed and nothing was flashed.")
            return 0

        if args.action == "status":
            config = _read_config(args.config)
            rootfs = workdir / "rootfs"
            print(f"Configuration: {args.config}")
            print(f"Device: {config.get('device', 'unset')}")
            print(f"Work directory: {workdir}")
            print(f"Arch rootfs: {'present' if (rootfs / 'usr/bin/pacman').is_file() else 'not installed'}")
            if rootfs.is_dir():
                for label, valid in inspect_rootfs(rootfs)["checks"].items():
                    print(f"{label}: {'OK' if valid else 'missing'}")
            return 0

        if args.action == "chroot":
            rootfs = workdir / "rootfs"
            if not (rootfs / "usr/bin/pacman").is_file():
                raise RuntimeError(f"Arch rootfs is missing: {rootfs}. Run alarmbootstrap install first.")
            return _run_chroot(rootfs, args.command)

        if args.action == "export":
            rootfs = workdir / "rootfs"
            if not (rootfs / "usr/bin/pacman").is_file():
                raise RuntimeError(f"Arch rootfs is missing: {rootfs}")
            destination = args.destination or (workdir / "export/alarmbootstrap-google-flame-rootfs.tar.gz")
            destination = destination.expanduser().resolve()
            if destination == rootfs or rootfs in destination.parents:
                raise RuntimeError("Export archive must be outside the rootfs directory.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                root_command([
                    "tar", "--numeric-owner", "--xattrs", "--acls", "-czf", str(destination),
                    "-C", str(rootfs), ".",
                ]),
                check=True,
            )
            print(f"Rootfs archive exported to: {destination}")
            return 0

        if args.action == "pixel4":
            rootfs = workdir / "rootfs"
            if args.pixel_action == "stage-kernel":
                if args.nura_rootfs is not None:
                    nura_source = args.nura_rootfs
                else:
                    nura_source = unpack_nura_packages(
                        args.nura_packages, workdir / "nura-package-staging"
                    )
                copied = stage_kernel(nura_source, rootfs)
                print("Reused existing Nura/postmarketOS SM8150 kernel stack:")
                for item in copied:
                    print(f"  {item}")
                print("Files staged only; this does not create or flash a bootable disk image.")
                return 0
            if args.pixel_action == "inspect":
                report = inspect_rootfs(rootfs)
                print(json.dumps(report, indent=2))
                return 0 if report["artifact_staging_complete"] else 1
            if args.pixel_action == "build-uboot":
                return run_uboot_build(args.flash, args.source, workdir / "uboot")
    except (
        RootfsError, Pixel4Error, OSError, ValueError, RuntimeError,
        json.JSONDecodeError, subprocess.CalledProcessError,
    ) as exc:
        print(f"alarmbootstrap: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
