# pmbootstrap

Sophisticated chroot/build/flash tool to develop and install
[postmarketOS](https://postmarketos.org).

## Development

Find the location of the upstream repository for pmbootstrap on the
[postmarketOS homepage](https://postmarketos.org/source-code/).

Run CI scripts locally with:

```sh
pmbootstrap ci
```

Run a single test file:

```sh
pytest -vv ./test/test_keys.py
```

## Issues

[Issues are being tracked in the GitLab issue tracker](https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/issues).

## Requirements

* Linux distribution on the host system (`x86`, `x86_64`, `aarch64` or `armv7`)
  * [Windows subsystem for Linux
    (WSL)](https://en.wikipedia.org/wiki/Windows_Subsystem_for_Linux) does
    **not** work! Please use [VirtualBox](https://www.virtualbox.org/) instead.
  * [Linux kernel 3.17 or higher](https://postmarketos.org/oldkernel)
  * Note: kernel versions between 5.8.8 and 6.0 might [have issues with
    parted](https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/issues/2309).
  * /tmp must be mounted with the `exec` flag. Mounting it with `noexec` breaks
    pmbootstrap. This is chiefly a concern for "hardened" kernels and OS:es. If
    you insist on having the `noexec` flag set, you can work around this issue
    by setting the `TMPDIR` environment variable to a directory with the
    executable flag set, e.g. `TMPDIR=$HOME/.tmp pmbootstrap chroot`.
* Python 3.10+
* For python3 < 3.11: tomli
* OpenSSL
* git 2.46+
* kpartx (from multipath-tools)
* losetup (with --json support, e.g. util-linux version)
* ps
* tar

## Relation to pmaports

For pmbootstrap to be useful, it needs to maintain a local copy of the
[pmaports](https://gitlab.postmarketos.org/postmarketOS/pmaports) repository
where postmarketOS-specific packages are maintained. This is set up
automatically, but the local copy of pmaports does not automatically get
updated. To update it, you can run `$ pmbootstrap pull`.

The latest pmbootstrap version works with currently [active postmarketOS
releases](https://wiki.postmarketos.org/wiki/Releases). Attempting to use
pmboostrap with old postmarketOS versions (old pmaports branches) may result in
failures and is not supported. See `pmbootstrap_min_version` in
[pmaports.cfg](https://wiki.postmarketos.org/wiki/Pmaports.cfg_reference) for
the oldest supported pmbootstrap version for a given pmaports revision. The
upper bound is not documented.

Please note that this compatibility guarantee does not apply to the the pmaports
testsuite—only the latest pmbootstrap from the "main" branch is guaranteed to
work with it.

## Usage Examples

Please refer to the [postmarketOS wiki](https://wiki.postmarketos.org) for
in-depth coverage of topics such as [porting to a new
device](https://wiki.postmarketos.org/wiki/Porting_to_a_new_device) or
[installation](https://wiki.postmarketos.org/wiki/Installation_guide). The help
output (`pmbootstrap -h`) has detailed usage instructions for every command.
Read on for some generic examples of what can be done with `pmbootstrap`.

### Installing pmbootstrap

<https://wiki.nura.eco/wiki/Pmbootstrap/Installation>

### Basics

Initial setup:

```sh
pmbootstrap init
```

Run this in a second window to see all shell commands that get executed:

```sh
pmbootstrap log
```

Quick health check and config overview:

```sh
pmbootstrap status
```

### Packages

Build `aports/main/hello-world`:

```sh
pmbootstrap build hello-world
```

Cross-compile to `armhf`:

```sh
pmbootstrap build --arch=armhf hello-world
```

Build with source code from local folder:

```sh
pmbootstrap build linux-postmarketos-mainline --src=~/code/linux
```

Update checksums:

```sh
pmbootstrap checksum hello-world
```

Generate a template for a new package:

```sh
pmbootstrap newapkbuild "https://gitlab.postmarketos.org/postmarketOS/tinydm/-/archive/1.2.0/tinydm-1.2.0.tar.gz"
```

#### Default architecture

Packages will be compiled for the architecture of the device running pmbootstrap
by default. For example, if your `x86_64` PC runs pmbootstrap, it would build a
package for `x86_64` with this command:

```sh
pmbootstrap build hello-world
```

If you would rather build for the target device selected in `pmbootstrap init`
by default, then use the `build_default_device_arch` option:

```sh
pmbootstrap config build_default_device_arch True
```

If your target device is `pine64-pinephone` for example, pmbootstrap will now
build this package for `aarch64`:

```sh
pmbootstrap build hello-world
```

### Chroots

Enter the `armhf` building chroot:

```sh
pmbootstrap chroot -b armhf
```

Run a command inside a chroot:

```sh
pmbootstrap chroot -- echo test
```

Safely delete all chroots:

```sh
pmbootstrap zap
```

### Device Porting Assistance

Analyze Android
[`boot.img`](https://wiki.postmarketos.org/wiki/Glossary#boot.img) files (also
works with recovery OS images like TWRP):

```sh
pmbootstrap bootimg_analyze ~/Downloads/twrp-3.2.1-0-fp2.img
```

Check kernel configs:

```sh
pmbootstrap kconfig check
```

Edit a kernel config:

```sh
pmbootstrap kconfig edit --arch=armhf postmarketos-mainline
```

### Root File System

Build the rootfs:

```sh
pmbootstrap install
```

Build the rootfs with full disk encryption:

```sh
pmbootstrap install --fde
```

Update existing installation on SD card:

```sh
pmbootstrap install --disk=/dev/mmcblk0 --rsync
```

Run the image in QEMU:

```sh
pmbootstrap qemu --image-size=1G
```

Flash to the device:

```sh
pmbootstrap flasher flash_kernel
pmbootstrap flasher flash_rootfs --partition=userdata
```

Export the rootfs, kernel, initramfs, `boot.img` etc.:

```sh
pmbootstrap export
```

Extract the initramfs

```sh
pmbootstrap initfs extract
```

Build and flash Android recovery zip:

```sh
pmbootstrap install --android-recovery-zip
pmbootstrap flasher --method=adb sideload
```

### Repository Maintenance

List pmaports that don't have a binary package:

```sh
pmbootstrap repo_missing --arch=armhf --overview
```

Increase the `pkgrel` for each aport where the binary package has outdated
dependencies (e.g. after soname bumps):

```sh
pmbootstrap pkgrel_bump --auto
```

Generate cross-compiler aports based on the latest version from Alpine's aports:

```sh
pmbootstrap aportgen gcc-armhf
```

Manually rebuild package index:

```sh
pmbootstrap index
```

Delete local binary packages without existing aport of same version:

```sh
pmbootstrap zap -m
```

### Debugging

Use `-v` on any action to get verbose logging:

```sh
pmbootstrap -v build hello-world
```

Parse a single APKBUILD and return it as JSON:

```sh
pmbootstrap apkbuild_parse hello-world
```

Parse a package from an APKINDEX and return it as JSON:

```sh
pmbootstrap apkindex_parse $WORK/cache_apk_x86_64/APKINDEX.8b865e19.tar.gz hello-world
```

`ccache` statistics:

```sh
pmbootstrap stats --arch=armhf
```

### Use alternative sudo

See `PMB_SUDO` in `docs/environment_variables.md`.

### Select SSH keys to include and make authorized in new images

If the config file option `ssh_keys` is set to `True` (it defaults to `False`),
then all files matching the glob `~/.ssh/*.pub` will be placed in
`~/.ssh/authorized_keys` in the user's home directory in newly-built images.

Sometimes, for example if you have a large number of SSH keys, you may wish to
select a different set of public keys to include in an image. To do this, set
the `ssh_key_glob` configuration parameter in the pmbootstrap config file to a
string containing a glob that is to match the file or files you wish to include.

For example, a `~/.config/pmbootstrap_v3.cfg` may contain:

```ini
[pmbootstrap]
# ...
ssh_keys = True
ssh_key_glob = ~/.ssh/postmarketos-dev.pub
# ...
```

## License

[GPLv3](LICENSE)
