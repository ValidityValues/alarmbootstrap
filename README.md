# alarmbootstrap

**Arch Linux ARM device bootstrapper based on pmbootstrap.** The first device profile is
Google Pixel 4 (google-flame), using the existing postmarketOS SM8150 kernel/device stack
and Andrew Gigena's andrew/google-flame U-Boot branch.

> **Development status:** early port. The upstream pmbootstrap codebase and tests are retained,
> but the Arch Linux ARM backend is being brought up incrementally. A generic AArch64 rootfs
> is not, by itself, a bootable Pixel 4 image. Do not flash a generated image until the boot path
> is verified and a recovery plan exists.

## What is included

- Original pmbootstrap source tree (GPL-3.0-or-later) retained as a compatibility/build base.
- Native alarmbootstrap command for configuration, Arch Linux ARM rootfs staging, device catalog
  synchronisation, export and Pixel 4 kernel-artifact staging.
- Initial google-flame profile referencing existing postmarketOS kernel, firmware and device
  packages; the project does not attempt to write replacement hardware drivers.
- Reproducible U-Boot build helper for andrew/google-flame, with flashing disabled by default.
- Device catalog importer for Nura/postmarketOS pmaports. Existing records are merged instead
  of silently deleted during future syncs.

The original pmbootstrap commands remain in the source. Commands that do not yet have an
Arch-native implementation are dispatched to the retained pmbootstrap compatibility layer;
those legacy actions still require a compatible pmaports/APK environment.

## Requirements

A Linux host is required. Windows Subsystem for Linux is not recommended for image/loop-device
work. Install these tools using your distribution's package manager:

- Python 3.10 or newer, Git, bsdtar (libarchive), tar, sudo, and GnuPG (`gpg`) for authenticating the rootfs
- fastboot and Android platform tools for the optional Pixel 4 bootloader step
- For U-Boot builds: make, an AArch64 cross compiler (aarch64-linux-gnu-gcc), bison,
  flex, swig, dtc, OpenSSL development headers and the mkbootimg utility
- At least 5 GiB free space for the compressed archive plus extracted rootfs; more is recommended

For cross-architecture chroot operations on an x86_64 host, a working AArch64 binfmt/QEMU
registration is required. The installer does not silently install or enable a host binfmt handler.

## Install alarmbootstrap

Clone the repository and install it in an isolated Python environment:

```sh
git clone https://github.com/ValidityValues/alarmbootstrap.git
cd alarmbootstrap
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
alarmbootstrap --help
```

To run the upstream pmbootstrap test suite, use the upstream CI/dev environment requirements
and the pmb compatibility code. Not every upstream integration test is expected to pass
without a local pmaports tree and APK tools.

## 1. Configure Pixel 4

Create the default configuration and working directory:

```sh
alarmbootstrap init --device google-flame
alarmbootstrap status
```

The default work directory is ~/.local/share/alarmbootstrap. Override it with --workdir.
The configuration file is ~/.config/alarmbootstrap/config.json by default.

## 2. Synchronise the full Nura device catalog

Device metadata and kernel recipes live in pmaports, not in pmbootstrap itself. Synchronise the
catalog from a local pmaports checkout (recommended), or let the command make a shallow clone:

```sh
git clone --depth=1 https://gitlab.postmarketos.org/postmarketOS/pmaports.git ~/pmaports
alarmbootstrap devices --sync-nura --ports-dir ~/pmaports
alarmbootstrap devices
```

The checked-in baseline preserves **670 unique device IDs** from 671 `deviceinfo` entries in the
pmaports mirror snapshot, including archived entries. Non-Pixel-4 records are metadata-only until
they have a reviewed Arch port; a catalog entry does not claim that a device boots Arch Linux ARM.
Syncing enriches records with literal `deviceinfo` fields. Existing IDs are preserved when upstream
changes, and removed entries are marked retired rather than discarded. To write the synchronized
catalog into a chosen checkout path, pass `--output devices/nura-catalog.json`.

## 3. Create an Arch Linux ARM AArch64 rootfs

```sh
alarmbootstrap install
```

By default this downloads the official generic AArch64 Arch Linux ARM root filesystem and
extracts it into $WORKDIR/rootfs. The installer verifies the detached PGP signature against the pinned Arch Linux ARM Build System
fingerprint `68B3537F39A313B3E574D06777193F152BDBE6A6`, then checks the published MD5 checksum as an
additional download-integrity check. Signature verification fails closed if GnuPG or the expected
signing key is unavailable. The archive is extracted with `bsdtar` to preserve numeric ownership,
ACLs and extended attributes. The command does not
flash, repartition or write to a connected device.

Useful options:

```sh
alarmbootstrap install --workdir ~/alarmbootstrap-work
alarmbootstrap install --url https://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz
alarmbootstrap install --force
```

--force only replaces the local rootfs directory inside the selected working directory.
Check that the work directory has enough free space before downloading.

## 4. Reuse the postmarketOS Pixel 4 kernel and drivers

Do **not** replace the SM8150 device stack with a generic kernel when preparing flame.
Use a working Nura/postmarketOS rootfs that contains the existing kernel package artifacts.
The current Nura package exposes `/boot/linux.efi`, `/boot/vmlinuz`,
`/boot/dtbs/qcom/sm8150-google-flame.dtb`, and `/lib/modules/*sm8150*`.

With a Nura rootfs available, stage the kernel artifacts into the Arch rootfs (this copies files only; it does not make the embedded Nura initramfs automatically compatible with Arch):

```sh
alarmbootstrap pixel4 stage-kernel --nura-rootfs /path/to/nura-rootfs
alarmbootstrap pixel4 inspect
```

The command copies the existing EFI kernel, SM8150 DTB, matching modules and available firmware;
it does not compile substitute drivers. It keeps the original Arch kernel files and places the
postmarketOS kernel under a separate name. A kernel/modules mismatch is a hard error. This is a
staging step, not proof that the kernel's embedded initramfs or command line can boot the Arch
rootfs; adapting that boot flow remains a required development task.

Nura's published device package currently depends on the existing linux-postmarketos-qcom-sm8150
kernel, firmware-google-flame, device-google-flame, and Qualcomm userspace packages. Their
availability and current paths should be checked before building a final boot image:
https://pkgs.nura.eco/package/main/postmarketos/aarch64/device-google-flame

## 5. Build U-Boot for Pixel 4

The helper clones the exact branch and applies the userdata blkmap preboot configuration described
for this device. It builds an Android boot image but does **not** flash it unless --flash is
passed explicitly.

```sh
./scripts/build-google-flame-uboot.sh
```

Before attempting any flash, ensure the bootloader is unlocked, save a known-good boot image using
a method supported by your device, and verify that fastboot detects exactly one device. Only then:

```sh
./scripts/build-google-flame-uboot.sh --flash
```

Flashing U-Boot to `boot` replaces the current boot partition. The script asks you to type
`FLASH boot`, checks that fastboot sees exactly one device and checks the reported product is
`flame`. It records the image SHA-256, but this is not a substitute for a tested recovery path. Do not use flash_rootfs or raw block-device commands on the phone unless you have
verified the nested-partition layout and the exact destination.

## 6. Enter and export the staged rootfs

```sh
alarmbootstrap chroot
alarmbootstrap export
```

AArch64 chroot on x86_64 requires QEMU/binfmt configured by the host. Export creates a compressed
tar archive of the rootfs for inspection or later image-building; it is **not** a ready-to-flash
Pixel 4 image.

## Existing pmbootstrap functionality

The imported upstream pmb/ code retains package-build, chroot, initramfs, image analysis,
network boot, QEMU, flashing, package and diagnostic commands. Non-native commands are delegated
to that compatibility implementation. They still depend on the original Alpine/APK/pmaports
workflow and are not yet equivalent to a fully ported Arch backend. Use them deliberately:

```sh
alarmbootstrap legacy status
alarmbootstrap legacy bootimg_analyze /path/to/boot.img
```

The Arch-native commands are init, devices, install, status, chroot, export and pixel4.
Run alarmbootstrap --help for the up-to-date syntax.

## Development and tests

```sh
python -m pytest
python -m compileall -q alarmbootstrap pmb
```

Hardware validation still requires a real Pixel 4. A successful host-side rootfs extraction does
not prove that U-Boot, EFI, storage, display, touch, Wi-Fi, Bluetooth, audio or GPU acceleration
work on the phone.
