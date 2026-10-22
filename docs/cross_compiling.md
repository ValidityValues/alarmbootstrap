# Cross Compiling

## Overview

When building packages, it might be necessary to use cross compilation
depending on the target architecture. Cross compilation is *not* necessary if
the target architecture can directly run on the host CPU (for example building
an `x86_64` or `x86` package on a `x86_64` CPU).

Multiple methods for cross compilation are implemented in pmbootstrap. For all
methods except `cross-native`, a foreign arch chroot (with the target
architecture) gets used during the build in addition to the native chroot.

<!-- markdownlint-disable MD013 MD033 -->
| Method                      | Native | Foreign | Speed  | Limitations                                                             |
|-----------------------------|--------|---------|--------|-------------------------------------------------------------------------|
| QEMU only                   |        | x       | slow   | So slow that it is desirable to<br>use other methods where possible.    |
| crossdirect<br>*(default)*  | x      | x       | medium | Cross compiler runs natively,<br>everything else goes through QEMU.     |
| cross-native                | x      |         | fast   | Cannot depend on libraries<br>(works for kernel, u-boot, etc.).         |
| cross-native2               | x      | x       | fast   | Works with e.g. meson build system.<br>Kernel builds not yet supported. |
<!-- markdownlint-enable -->

## Methods

### QEMU only

Enable this method with `options="!pmb:crossdirect"` in the `APKBUILD`.

This method is the most reliable, but also the slowest. We only use it if
faster methods don't work. GTK projects using `g-ir-scanner` (*"Generating
[…].gir with a custom command"*) are currently [known to
fail](https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/issues/2567)
with other methods.

### Crossdirect

This is the default method.

This method works for almost all packages, and gives a good speed improvement
over running everything in QEMU. However only the cross compilers run natively.
Linkers and all other commands used during the build still need to run through
QEMU and so these are still very slow.

The native chroot gets mounted in the foreign arch chroot at `/native`. The
[crossdirect](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/blob/main/cross/crossdirect/APKBUILD)
package gets installed into the native chroot and creates wrapper scripts
pointing to the cross compilers. When building packages for `armv7`, the build
runs in the foreign chroot and `PATH` will get prepended with
`/native/usr/lib/crossdirect/armv7`. This leads to invoking the cross compiler
from the native chroot, running at native speed, whenever calling the compiler
from the foreign arch chroot.

### Cross-Native

Enable this method with `options="pmb:cross-native"` in the `APKBUILD`.

This method is only supported for packages that do not depend on foreign arch
libraries, such bare metal software (kernel, u-boot), firmware packages or the
postmarketos-artwork package.

The whole build is done in the native chroot. Environment variables are used
to tell abuild that it is a different arch package (`CARCH`) and to the
kernel-style Makefiles that the cross compilers should be used.

### Cross-Native2

Enable this method with `options="pmb:cross-native2"` in the `APKBUILD`.
This is supported since pmbootstrap 3.4, previous versions will ignore this
option and use the crossdirect method instead.

Packages from `makedepends_build=` in the `APKBUILD` are installed in the
native chroot (where we run the build), and packages from `makedepends_host=`
in the foreign chroot. Environment variables are used to run abuild in the
native chroot and use its cross compilation features rather than running it and
the build system through QEMU. This massively speeds up building when it works.

The foreign chroot is mounted into the native chroot at `/sysroot`. Most build
systems will refer to it as "sysroot", in abuild it is `CBUILDROOT`.

Packages have been built successfully with cross-native2 and the following
build systems:

* meson
* go build

Where possible, we should try to migrate all packages that currently use
crossdirect to cross-native2 to make them build faster.

## Language-specific

### Rust

Rust packages can either be built with QEMU only, or with the crossdirect
method. **Now that we have cross-native2 it makes more sense to try to get
rust support working there as it will be faster and more reliable.** Rust
support in crossdirect is still experimental.
[pmaports!4234](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/merge_requests/4234)
(cross/crossdirect: improve rust handling) describes some of the problems with
this approach.

#### CARGO\_HOME

If a program needs to download git repositories of dependencies with cargo
(ideally they are bundled with the source tarball and don't need to be
downloaded), then these git repositories are cached with pmbootstrap. This
works as long as the program does not override
[CARGO\_HOME](https://doc.rust-lang.org/cargo/guide/cargo-home.html). GNOME
podcasts does this for example, so if building gnome-podcasts from the git
repository with `pmbootstrap build --src`, patch out the override of
`CARGO_HOME` so the dependencies do not get downloaded for every build.

#### Packaging caveats

* `cargo auditable build` is unsupported with crossdirect and falls back to
  compiling in QEMU. Change it to `cargo build` to build the package with the
  native compiler.
* Running tests doesn't really work (e.g. when building squeekboard, the tests
  hang and time out).

## Detecting cross-compilation

Sometimes, it might be desirable to have conditional logic in `APKBUILD` files
that is only executed when no cross-compilation or only certain methods of
cross-compilation are in use. For example, certain testsuites might fail if ran
with `qemu-user`.

pmbootstrap exposes the `PMB_CROSS` variable at package build time, which is
set to either `unnecessary`, `qemu-only`, `crossdirect`, `cross-native` or
`cross-native2`, depending on which method is currently in use.

To then conditionally only run tests when running natively, you can do
something like this in an `APKBUILD`:

```shell
check() {
  if [ "$PMB_CROSS" = "unnecessary" ]; then
    meson test -C build
  fi
}
```
