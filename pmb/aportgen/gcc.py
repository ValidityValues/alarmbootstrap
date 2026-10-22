# Copyright 2025 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import fnmatch
import logging

import pmb.aportgen.core
import pmb.helpers.git
import pmb.helpers.run
from pmb.core.arch import Arch
from pmb.core.context import get_context
from pmb.core.pkgrepo import pkgrepo_default_path


def depends_for_sonames(libraries: dict[str, str], arch_libc: Arch) -> list[str]:
    """
    Get packages providing specific sonames from Alpine's main repo. Usually
    this would be done during package builds using abuild's "tracedeps". But
    this leads to our cross gccs immediately breaking once Alpine gcc packages
    change. So we figure out depends on our own here.
    """
    apkindex_main = pmb.helpers.repo.alpine_apkindex("main", arch_libc)
    providers = pmb.parse.apkindex.parse(apkindex_main, True)

    result: dict[str, str] = {}
    for pattern_soname in libraries:
        pattern_pkgname = libraries[pattern_soname]

        for provide, packages in providers.items():
            if not fnmatch.fnmatch(provide, pattern_soname):
                continue
            match = None
            for pkgname in packages:
                if fnmatch.fnmatch(pkgname, pattern_pkgname):
                    logging.info(f"{provide}: provided by {pkgname}")
                    match = pkgname
                    # No break, so it prints other matches too if any. This
                    # should make debugging easier if something goes wrong.
                else:
                    logging.warning(
                        f"{provide}: provided by {pkgname} which is an unexpected pkgname, ignoring..."
                    )
            if match:
                if pattern_soname in result:
                    old = result[pattern_soname].split(".so.")[1]
                    new = provide.split(".so.")[1]
                    if pmb.parse.version.compare(new, old) == 1:
                        logging.debug(
                            f"{provide}: new highest version found for pattern {pattern_soname}"
                        )
                        result[pattern_soname] = provide
                else:
                    logging.debug(f"{provide}: first version found for pattern {pattern_soname}")
                    result[pattern_soname] = provide

        if pattern_soname not in result:
            raise RuntimeError(
                f"{pattern_soname}: is not provided by any package, can't trace dependencies for this pattern."
            )

    return list(result.values())


def generate(pkgname: str) -> None:
    # Copy original aport
    prefix = pkgname.split("-", maxsplit=1)[0]
    arch = Arch.from_str(pkgname.split("-")[1])
    # Until pmb#2517 is resolved properly, we set the tracedeps manually. The
    # musl soname contains the architecture name, support cross compiling from
    # aarch64 to x86_64 and x86_64 to all other arches.
    host_arches = [Arch.from_str(a) for a in pmb.aportgen.get_cross_package_arches(pkgname).split()]
    arch_libc = host_arches[0]
    context = get_context()
    if prefix == "gcc":
        upstream = pmb.aportgen.core.get_upstream_aport("gcc", arch)
        based_on = "main/gcc (from Alpine)"
    elif prefix == "gcc4":
        upstream = pkgrepo_default_path() / "main/gcc4"
        based_on = "main/gcc4 (from postmarketOS)"
    elif prefix == "gcc6":
        upstream = pkgrepo_default_path() / "main/gcc6"
        based_on = "main/gcc6 (from postmarketOS)"
    else:
        raise ValueError(f"Invalid prefix '{prefix}', expected gcc, gcc4 or gcc6.")
    pmb.helpers.run.user(["cp", "-r", upstream, context.config.work / "aportgen"])

    # Rewrite APKBUILD
    fields = {
        "pkgname": pkgname,
        "pkgdesc": f"Stage2 cross-compiler for {arch}",
        "arch": pmb.aportgen.get_cross_package_arches(pkgname),
        "depends": f"binutils-{arch} mpc1",
        "makedepends_build": "gcc g++ bison flex texinfo gawk zip"
        " gmp-dev mpfr-dev mpc1-dev zlib-dev",
        "makedepends_host": "linux-headers gmp-dev mpfr-dev mpc1-dev isl-dev"
        f" zlib-dev musl-dev-{arch} binutils-{arch}",
        "subpackages": "",
        # gcc6: options is already there, so we need to replace it and not only
        # set it below the header like done below.
        # !tracedeps: workaround for issue 2517
        "options": "!strip !tracedeps toolchain",
        "provides": "cmd:$CTARGET-gcc=$pkgver-r$pkgrel",
        "LIBGOMP": "false",
        "LIBGCC": "false",
        "LIBATOMIC": "false",
        "LIBITM": "false",
    }

    libraries = {
        "so:libgcc_s.so.*": "libgcc",
        "so:libgmp.so.*": "gmp",
        "so:libisl.so.*": "isl*",
        "so:libmpc.so.*": "mpc1",
        "so:libmpfr.so.*": "mpfr4",
        "so:libstdc++.so.*": "libstdc++",
        "so:libz.so.*": "zlib",
    }
    logging.info(f"*** Getting sonames for depends (arch_libc: {arch_libc})")
    fields["depends"] += f" {' '.join(depends_for_sonames(libraries, arch_libc))}"

    # Latest gcc only, not gcc4 and gcc6
    if prefix == "gcc":
        fields["subpackages"] = f"g++-{arch}:gpp libstdc++-dev-{arch}:libcxx_dev"

    below_header = (
        "CTARGET_ARCH="
        + str(arch)
        + """
        CTARGET="$(arch_to_hostspec ${CTARGET_ARCH})"
        LANG_D=false
        LANG_OBJC=false
        LANG_JAVA=false
        LANG_GO=false
        LANG_FORTRAN=false
        LANG_ADA=false
        options="!strip"

        # abuild doesn't try to tries to install "build-base-$CTARGET_ARCH"
        # when this variable matches "no*"
        BOOTSTRAP="nobuildbase"

        # abuild will only cross compile when this variable is set, but it
        # needs to find a valid package database in there for dependency
        # resolving, so we set it to /.
        CBUILDROOT="/"

        _cross_configure="--disable-bootstrap --with-sysroot=/usr/$CTARGET"
    """
    )

    libraries_gpp = {
        "so:libgmp.so.*": "gmp",
        "so:libisl.so.*": "isl*",
        "so:libmpc.so.*": "mpc1",
        "so:libmpfr.so.*": "mpfr4",
        "so:libz.so.*": "zlib",
    }
    logging.info(f"*** Getting sonames for depends in gpp subpackage (arch_libc: {arch_libc})")
    depends_gpp = " ".join(depends_for_sonames(libraries_gpp, arch_libc))

    # musl soname must be set conditionally by abuild in the APKBUILD since it
    # depends on the host arch
    musl_case_lines = '\ncase "$CARCH" in\n'
    for host_arch in host_arches:
        musl_soname = depends_for_sonames({f"so:libc.musl-{host_arch}.so.*": "musl"}, host_arch)[0]
        musl_case_lines += f'{host_arch}) depends="$depends {musl_soname}" ;;\n'
    musl_case_lines += "esac"
    # for gpp():
    musl_case_lines_indented = musl_case_lines.replace("\n", "\n\t")

    replace_simple = {
        # Do not package libstdc++, do not add "g++-$ARCH" here (already
        # did that explicitly in the subpackages variable above, so
        # pmbootstrap picks it up properly).
        '*subpackages="$subpackages libstdc++:libcxx:*': None,
        # We set the cross_configure variable at the beginning, so it does not
        # use CBUILDROOT as sysroot. In the original APKBUILD this is a local
        # variable, but we make it a global one.
        "*_cross_configure=*": None,
        # Do not build foreign arch libgcc, we use the one from Alpine (#2168)
        "_libgcc=true*": "_libgcc=false",
        # Keep the cross prefix in package()
        "*# These are moved into packages with arch=*": "",
        "*# cross prefix (doesn't exist when BOOTSTRAP=nolibc)*": "",
        '*BOOTSTRAP" != nolibc ] && mv *': "",
        # Add depends and musl case block to the gpp subpackage, so we don't need to use tracedeps
        "*amove $_gcclibexec/cc1plus*": f'\tdepends="$depends {depends_gpp}"\n{musl_case_lines_indented}\n\n\tamove $_gcclibexec/cc1plus',
        # Disable libsanitizer for e.g. aarch64 -> x86_64 gcc (pma!6722)
        '*_sanitizer_configure="--enable-libsanitizer"*': "",
        # inject musl soname case statement, which depends on $depends, after
        # depends=
        f'depends="{fields["depends"]}"': f'depends="{fields["depends"]}"\n{musl_case_lines}',
    }

    pmb.aportgen.core.rewrite(
        pkgname, based_on, fields, replace_simple=replace_simple, below_header=below_header
    )
