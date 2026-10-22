# Copyright 2023 Pablo Castellano, Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re
import shutil
import signal
from pathlib import Path
from types import FrameType

import pmb.chroot
import pmb.chroot.apk
import pmb.helpers.run
import pmb.install.losetup
import pmb.parse.cpuinfo
from pmb.core import Chroot, ChrootType
from pmb.core.arch import Arch
from pmb.core.config import Config
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError
from pmb.types import Env, RunOutputTypeDefault


def system_image(device: str) -> Path:
    """
    Returns path to rootfs for specified device. In case that it doesn't
    exist, raise and exception explaining how to generate it.
    """
    path = Chroot.native() / "home/pmos/rootfs" / f"{device}.img"
    if not path.exists():
        logging.debug(f"Could not find rootfs: {path}")
        raise NonBugError(
            "The rootfs has not been generated yet, please run 'pmbootstrap install' first."
        )
    return path


def create_second_storage(size: str, device: str) -> Path:
    """
    Generate a second storage image if it does not exist.

    :returns: path to the image or None

    """
    path = Chroot.native() / "home/pmos/rootfs" / f"{device}-2nd.img"
    pmb.helpers.run.root(["touch", path])
    pmb.helpers.run.root(["chmod", "a+w", path])
    resize_image(size, path)
    return path


def which_qemu(arch: Arch) -> str:
    """Finds the qemu executable or raises an exception otherwise"""
    executable = "qemu-system-" + arch.qemu_system()
    if shutil.which(executable):
        return executable
    else:
        raise NonBugError(
            f"Could not find the '{executable}' executable in your PATH."
            "  Please install it in order to run qemu."
        )


def command_qemu(
    config: Config,
    arch: Arch,
    qemu_audio: str | None,
    qemu_cpu: str | None,
    qemu_display: str,
    memory_size: int,
    port_ssh: int,
    use_host_qemu: bool,
    use_qemu_gl: bool,
    use_qemu_kvm: bool,
    use_qemu_tablet: bool,
    img_path: Path,
    img_path_2nd: Path | None = None,
) -> tuple[list[str | Path], Env]:
    """Generate the full qemu command with arguments to run postmarketOS"""
    chroot_native = Chroot.native()
    chroot_target = Chroot.buildroot(arch)

    ncpus = os.cpu_count()
    if not ncpus:
        logging.warning("Couldn't get cpu count, defaulting to 4")
        ncpus = 4

    # QEMU mach-virt's max CPU count is 8, limit it so it will work correctly
    # on systems with more than 8 CPUs
    if not arch.is_native() and ncpus > 8:
        ncpus = 8

    env: Env
    # It might be tempting to use PathString here, but I don't think it makes sense semantically as
    # this is not just a list of paths.
    command: list[str | Path]

    if use_host_qemu:
        qemu_bin = which_qemu(arch)
        env = {}
        command = [qemu_bin]
    else:
        env = {
            "QEMU_MODULE_DIR": chroot_native / "usr/lib/qemu",
            "GBM_DRIVERS_PATH": chroot_native / "usr/lib/xorg/modules/dri",
            "LIBGL_DRIVERS_PATH": chroot_native / "usr/lib/xorg/modules/dri",
        }

        if "gtk" in qemu_display:
            env.update(
                {
                    "GTK_THEME": "Default",
                    "XDG_DATA_DIRS": ":".join(
                        [
                            str(chroot_native / "usr/local/share"),
                            str(chroot_native / "usr/share"),
                        ]
                    ),
                }
            )

        command = []
        if Arch.native() in [Arch.aarch64, Arch.armv7]:
            # Workaround for QEMU failing on aarch64 asymmetric multiprocessor
            # arch (big/little architecture
            # https://en.wikipedia.org/wiki/ARM_big.LITTLE) see
            # https://bugs.linaro.org/show_bug.cgi?id=1443
            ncpus_bl = pmb.parse.cpuinfo.arm_big_little_first_group_ncpus()
            if ncpus_bl:
                ncpus = ncpus_bl
                logging.info(
                    "QEMU will run on big/little architecture on the"
                    f" first {ncpus} cores (from /proc/cpuinfo)"
                )
                command += [chroot_native / "lib" / f"ld-musl-{Arch.native()}.so.1"]
                command += [chroot_native / "usr/bin/taskset"]
                command += ["-c", "0-" + str(ncpus - 1)]

        command += [chroot_native / "lib" / f"ld-musl-{Arch.native()}.so.1"]
        command += [
            "--library-path="
            + ":".join(
                [
                    str(chroot_native / "lib"),
                    str(chroot_native / "usr/lib"),
                    str(chroot_native / "usr/lib/pulseaudio"),
                ]
            )
        ]
        command += [chroot_native / "usr/bin" / f"qemu-system-{arch.qemu_system()}"]
        command += ["-L", chroot_native / "usr/share/qemu/"]

    command += ["-nodefaults"]
    command += ["-smp", str(ncpus)]
    command += ["-m", str(memory_size)]

    command += ["-serial"]
    if config.qemu_redir_stdio:
        command += ["mon:stdio"]
    else:
        command += ["stdio"]

    command += ["-drive", f"file={img_path},format=raw,if=virtio"]
    if img_path_2nd:
        command += ["-drive", f"file={img_path_2nd}" + ",format=raw,if=virtio"]

    if use_qemu_tablet:
        command += ["-device", "virtio-tablet-pci"]
    else:
        command += ["-device", "virtio-mouse-pci"]
    command += ["-device", "virtio-keyboard-pci"]
    command += ["-netdev", f"user,id=net,hostfwd=tcp:127.0.0.1:{port_ssh}-:22"]
    command += ["-device", "virtio-net-pci,netdev=net"]

    # Check that arch is supported by pmb qemu
    if arch not in [
        Arch.x86_64,
        Arch.aarch64,
        Arch.riscv64,
        Arch.ppc64le,
        Arch.loongarch64,
        Arch.armv7,
    ]:
        raise RuntimeError(f"Architecture {arch} not supported by this command yet.")

    # Apply arch-specific qemu config
    match arch:
        case Arch.armv7:
            command += ["-M", "virt"]
            command += ["-cpu", "cortex-a15"]
        case Arch.aarch64:
            command += ["-M", "virt"]
            command += ["-cpu", "cortex-a57"]
        case Arch.riscv64:
            command += ["-M", "virt"]
        case Arch.ppc64le:
            command += ["-M", "pseries"]
        case Arch.loongarch64:
            command += ["-M", "virt"]
        case _:
            pass

    # Configure display
    if qemu_display != "none":
        match arch:
            case Arch.x86_64:
                command += ["-device", "virtio-vga-gl"]
            case Arch.aarch64 | Arch.armv7:
                command += ["-device", "virtio-gpu-gl"]
            case Arch.riscv64 | Arch.ppc64le | Arch.loongarch64:
                command += ["-device", "virtio-gpu-pci"]
            case _:
                raise RuntimeError(f"Missing gpu device case for {arch}")

    host_arch = Arch.native()
    edk2_chroot = chroot_native.path if arch == host_arch else chroot_target.path
    match arch:
        case Arch.aarch64:
            command += [
                "-drive",
                f"if=pflash,format=raw,readonly=on,file={edk2_chroot}/usr/share/AAVMF/AAVMF_CODE.fd",
            ]
        case Arch.x86_64:
            command += [
                "-drive",
                f"if=pflash,format=raw,readonly=on,file={edk2_chroot}/usr/share/OVMF/OVMF.fd",
            ]
        case Arch.loongarch64:
            command += [
                "-drive",
                f"if=pflash,format=raw,readonly=on,file={edk2_chroot}/usr/share/edk2/loongarch64/QEMU_EFI.fd",
            ]
        case Arch.ppc64le:
            # ppc64le uses SLOF included in QEMU
            pass
        case Arch.riscv64:
            command += [
                "-drive",
                f"if=pflash,format=raw,readonly=on,file={edk2_chroot}/usr/share/edk2/riscv/RISCV_VIRT_CODE.fd",
            ]
        case _:
            raise RuntimeError(f"Architecture {arch} not configured for EFI support.")

    # Kernel Virtual Machine (KVM) support
    native = pmb.parse.deviceinfo().arch.is_native()
    if use_qemu_kvm and native and os.path.exists("/dev/kvm"):
        command += ["-enable-kvm"]
        command += ["-cpu", "host"]
    else:
        logging.info("WARNING: QEMU is not using KVM and will run slower!")

    if qemu_cpu:
        command += ["-cpu", qemu_cpu]

    display = qemu_display
    if display != "none":
        display += ",show-cursor=on,gl=" + ("on" if use_qemu_gl else "off")

    # Separate -show-cursor option is deprecated. If your host qemu fails here,
    # it's old (#1995).
    command += ["-display", f"{display}"]

    # Audio support
    if qemu_audio:
        command += ["-audio", f"{qemu_audio},model=hda"]

    return (command, env)


def resize_image(img_size_new: str, img_path: Path) -> None:
    """
    Truncates an image to a specific size. The value must be larger than the
    current image size, and it must be specified in MiB or GiB units (powers of
    1024).

    :param img_size_new: new image size in M or G
    :param img_path: the path to the image
    """
    # Current image size in bytes
    img_size = os.path.getsize(img_path)

    # Make sure we have at least 1 integer followed by either M or G
    pattern = re.compile(r"^[0-9]+[M|G]$")
    if not pattern.match(img_size_new):
        raise RuntimeError("IMAGE_SIZE must be in [M]iB or [G]iB, e.g. 2048M or 2G")

    # Remove M or G and convert to bytes
    img_size_new_bytes = int(img_size_new[:-1]) * 1024 * 1024

    # Convert further for G
    if img_size_new[-1] == "G":
        img_size_new_bytes = img_size_new_bytes * 1024

    if img_size_new_bytes >= img_size:
        logging.info(f"Resize image to {img_size_new}: {img_path}")
        pmb.helpers.run.root(["truncate", "-s", img_size_new, img_path])
    else:
        # Convert to human-readable format
        # NOTE: We convert to M here, and not G, so that we don't have to
        # display a size like 1.25G, since decimal places are not allowed by
        # truncate.
        # We don't want users thinking they can use decimal numbers, and so in
        # this example, they would need to use a size greater then 1280M
        # instead.
        img_size_str = str(round(img_size / 1024 / 1024)) + "M"

        raise RuntimeError(f"IMAGE_SIZE must be {img_size_str} or greater")


def _sigterm_handler(_number: int, _stack_frame: FrameType | None) -> None:
    raise RuntimeError(
        "pmbootstrap was terminated by another process, and killed the QEMU VM it was running."
    )


def install_depends(arch: Arch) -> None:
    """Install any necessary qemu dependencies in native chroot"""
    depends = [
        "mesa-dri-gallium",
        "mesa-egl",
        "mesa-gl",
        "qemu",
        "qemu-audio-alsa",
        "qemu-audio-pa",
        "qemu-audio-sdl",
        "qemu-hw-display-virtio-gpu",
        "qemu-hw-display-virtio-gpu-gl",
        "qemu-hw-display-virtio-gpu-pci",
        "qemu-hw-display-virtio-gpu-pci-gl",
        "qemu-hw-display-virtio-vga",
        "qemu-hw-display-virtio-vga-gl",
        "qemu-system-" + arch.qemu_system(),
        "qemu-ui-gtk",
        "qemu-ui-opengl",
        "qemu-ui-sdl",
    ]

    chroot = Chroot.native()
    pmb.chroot.init(chroot)
    pmb.chroot.apk.install(depends, chroot)


def install_efi_image(arch: Arch) -> None:
    edk2_pkg = None

    # EDK2 builds are only available for the target architecture
    match arch:
        case Arch.aarch64:
            edk2_pkg = "aavmf"
        case Arch.x86_64:
            edk2_pkg = "ovmf"
        case Arch.loongarch64:
            edk2_pkg = "edk2-loongarch64"
        case Arch.ppc64le:
            # ppc64le uses SLOF included in QEMU instead of EFI
            return
        case Arch.riscv64:
            edk2_pkg = "ovmf"
        case _:
            raise RuntimeError(f"Architecture {arch} not configured for EFI support.")

    # If we're running natively, install it to the native chroot, otherwise we need to
    # install it in the target chroot
    target_chroot = Chroot.native() if arch == Arch.native() else Chroot.buildroot(arch)
    pmb.chroot.init(target_chroot)
    pmb.chroot.apk.install([edk2_pkg], target_chroot)


def qemu(
    qemu_audio: str | None,
    qemu_cpu: str | None,
    qemu_display: str,
    memory_size: int,
    image_size: str | None,
    second_storage: str | None,
    port_ssh: int,
    use_host_qemu: bool,
    use_qemu_gl: bool,
    use_qemu_kvm: bool,
    use_qemu_tablet: bool,
) -> None:
    """Run a postmarketOS image in qemu"""
    config = get_context().config
    device = config.device
    arch = pmb.parse.deviceinfo().arch

    # Make sure the rootfs image isn't mounted
    pmb.mount.umount_all(Chroot(ChrootType.IMAGE, "").path)
    pmb.install.losetup.detach_all()

    img_path = system_image(device)
    img_path_2nd = None
    if second_storage:
        img_path_2nd = create_second_storage(second_storage, device)

    if not use_host_qemu:
        install_depends(arch)
    install_efi_image(arch)

    logging.info("Running postmarketOS in QEMU VM (" + arch.qemu_system() + ")")

    qemu, env = command_qemu(
        config,
        arch,
        qemu_audio,
        qemu_cpu,
        qemu_display,
        memory_size,
        port_ssh,
        use_host_qemu,
        use_qemu_gl,
        use_qemu_kvm,
        use_qemu_tablet,
        img_path,
        img_path_2nd,
    )

    # Workaround: QEMU runs as local user and needs write permissions in the
    # rootfs, which is owned by root
    if not os.access(img_path, os.W_OK):
        pmb.helpers.run.root(["chmod", "666", img_path])

    # Resize the rootfs (or show hint)
    if image_size:
        resize_image(image_size, img_path)
    else:
        logging.info(
            "NOTE: Run 'pmbootstrap qemu --image-size 2G' to set"
            " the rootfs size when you run out of space!"
        )

    # SSH/serial/network hints
    logging.info("Connect to the VM:")
    logging.info(f"* (ssh) ssh -p {port_ssh} {config.user}@localhost")
    logging.info("* (serial) in this console (stdout/stdin)")

    if config.qemu_redir_stdio:
        logging.info(
            "NOTE: Ctrl+C is redirected to the VM! To disable this, "
            "run: pmbootstrap config qemu_redir_stdio False"
        )
        logging.info("NOTE: To quit QEMU with this option you can use Ctrl-A, X.")

    if config.ui == "none":
        logging.warning(
            "WARNING: With UI=none network doesn't work"
            " automatically: https://postmarketos.org/qemu-network"
        )

    # Run QEMU and kill it together with pmbootstrap
    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
        pmb.helpers.run.user(qemu, output=RunOutputTypeDefault.TUI, env=env)
    except KeyboardInterrupt:
        # In addition to not showing a trace when pressing ^C, let user know
        # they can override this behavior:
        logging.info("Quitting because Ctrl+C detected.")
        logging.info("To override this behavior and have pmbootstrap send Ctrl+C to the VM, run:")
        logging.info("$ pmbootstrap config qemu_redir_stdio True")
