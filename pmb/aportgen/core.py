# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import fnmatch
import re
from pathlib import Path

import pmb.helpers.git
import pmb.helpers.run
from pmb.core import Chroot
from pmb.core.arch import Arch
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError


def indent_size(line: str) -> int:
    """Number of spaces at the beginning of a string."""
    matches = re.findall(r"^[ ]*", line)
    if len(matches) == 1:
        return len(matches[0])
    return 0


def format_function(name: str, body: str, remove_indent: int = 4) -> str:
    """
    Format the body of a shell function passed to rewrite() below, so it fits
    the format of the original APKBUILD.

    :param remove_indent: Maximum number of spaces to remove from the
        beginning of each line of the function body.
    """
    tab_width = 4
    ret = ""
    lines = body.split("\n")
    for i in range(len(lines)):
        line = lines[i]
        if not line.strip() and (not ret or i == len(lines) - 1):
            continue

        # Remove indent
        spaces = min(indent_size(line), remove_indent)
        line = line[spaces:]

        # Convert spaces to tabs
        spaces = indent_size(line)
        tabs = int(spaces / tab_width)
        line = ("\t" * tabs) + line[spaces:]

        ret += line + "\n"
    return name + "() {\n" + ret + "}\n"


def rewrite(
    pkgname: str,
    path_original: Path | str | None = None,
    fields: dict[str, str] = {},
    replace_pkgname: str | None = None,
    replace_functions: dict[str, str | None] = {},
    replace_simple: dict[str, str | None] = {},
    below_header: str = "",
    remove_indent: int = 4,
) -> None:
    """
    Append a header to $WORK/aportgen/APKBUILD, delete maintainer/contributor
    lines (so they won't be bugged with issues regarding our generated aports),
    and add reference to the original aport.

    :param path_original: The original path of the automatically generated
        aport.
    :param fields: key-value pairs of fields that shall be changed in the
        APKBUILD. For example: {"pkgdesc": "my new package", "subpkgs": ""}
    :param replace_pkgname: When set, $pkgname gets replaced with that string
        in every line.
    :param replace_functions: Function names and new bodies, for example:
        {"build": "return 0"}
        The body can also be None (deletes the function)
    :param replace_simple: Lines that fnmatch the pattern, get
        replaced/deleted. Example: {"*test*": "# test", "*mv test.bin*": None}
    :param below_header: String that gets directly placed below the header.
    :param remove_indent: Number of spaces to remove from function body
        provided to replace_functions.

    """
    # Header
    if path_original:
        lines_new = [
            "# Automatically generated aport, do not edit!\n",
            f"# Generator: pmbootstrap aportgen {pkgname}\n",
            f"# Based on: {path_original}\n",
        ]
    else:
        lines_new = [
            "# Forked from Alpine INSERT-REASON-HERE (CHANGEME!)\n",
        ]

    line: str | None
    if below_header:
        for line in below_header.split("\n"):
            if not line[:8].strip():
                line = line[8:]
            lines_new += line.rstrip() + "\n"

    # Copy/modify lines, skip Contributor
    path = get_context().config.work / "aportgen/APKBUILD"
    with open(path, "r+", encoding="utf-8") as handle:
        skip_in_func = False
        have_maintainer = False
        for line in handle:
            # Clear maintainer line
            if line.startswith(("# Maintainer", "maintainer=")):
                if have_maintainer:
                    line = ""  # APKBUILDs may use the variable + comment
                else:
                    line = 'maintainer="YOUR NAME (CHANGEME!) <EMAIL-ADDRESS@EXAMPLE.COM>"\n'
                    have_maintainer = True

            # Contributor
            if line.startswith("# Contributor"):
                continue

            # Replace functions
            if skip_in_func:
                if line.startswith("}"):
                    skip_in_func = False
                continue
            else:
                for func, body in replace_functions.items():
                    if line.startswith(func + "() {"):
                        skip_in_func = True
                        if body:
                            lines_new += format_function(func, body, remove_indent=remove_indent)
                        break
                if skip_in_func:
                    continue

            # Replace fields
            for key, value in fields.items():
                if line.startswith(key + "="):
                    if value:
                        if key in ["pkgname", "pkgver", "pkgrel"]:
                            # No quotes to avoid lint error
                            line = f"{key}={value}\n"
                        else:
                            line = f'{key}="{value}"\n'
                    else:
                        # Remove line without value to avoid lint error
                        line = ""
                    break

            # Replace $pkgname
            if replace_pkgname and "$pkgname" in line:
                line = line.replace("$pkgname", replace_pkgname)

            # Replace simple
            for pattern, replacement in replace_simple.items():
                if fnmatch.fnmatch(line, pattern + "\n"):
                    if line := replacement:
                        line += "\n"
                    break
            if line is None:
                continue

            lines_new.append(line)

        # Write back
        handle.seek(0)
        handle.write("".join(lines_new))
        handle.truncate()


def get_upstream_aport(pkgname: str, arch: Arch | None = None, retain_branch: bool = False) -> Path:
    """
    Perform a git checkout of Alpine's aports and get the path to the aport.

    :param pkgname: package name
    :param arch: Alpine architecture (e.g. "armhf"), defaults to native arch
    :returns: absolute path on disk where the Alpine aport is checked out
              example: /opt/pmbootstrap_work/cache_git/aports/upstream/main/gcc
    """
    arch = arch or Arch.native()
    # APKBUILD
    pmb.helpers.git.clone("aports_upstream")
    aports_upstream_path = get_context().config.work / "cache_git/aports_upstream"

    if retain_branch:
        logging.info("Not changing aports branch as --fork-alpine-retain-branch was used.")
    else:
        # Checkout branch
        channel_cfg = pmb.config.pmaports.read_config_channel()
        branch = channel_cfg["branch_aports"]
        logging.info(f"Checkout aports.git branch: {branch}")
        if pmb.helpers.run.user(["git", "switch", branch], aports_upstream_path, check=False):
            logging.info("NOTE: run 'pmbootstrap pull' and try again")
            logging.info(
                "NOTE: if it still fails, your aports.git was cloned with"
                " an older version of pmbootstrap, as shallow clone."
                " Unshallow it, or remove it and let pmbootstrap clone it"
                f" again: {aports_upstream_path}"
            )
            raise RuntimeError("Branch switch failed.")

    # Search package
    paths = list(aports_upstream_path.glob(f"*/{pkgname}"))
    if len(paths) > 1:
        raise RuntimeError("Package " + pkgname + " found in multiple aports subfolders.")
    elif len(paths) == 0:
        raise NonBugError(
            f"Package {pkgname} not found in alpine aports repository. Maybe it's a subpackage of a different origin package?"
        )
    aport_path = paths[0]

    # Parse APKBUILD
    apkbuild = pmb.parse.apkbuild(aport_path, check_pkgname=False)
    apkbuild_version = apkbuild["pkgver"] + "-r" + apkbuild["pkgrel"]

    # Binary package
    split = aport_path.parts
    repo = split[-2]
    pkgname = split[-1]
    # Update or create APKINDEX for relevant arch so we know it exists and is recent.
    pmb.helpers.repo.update(arch)
    index_path = pmb.helpers.repo.alpine_apkindex(repo, arch)
    package = pmb.parse.apkindex.package(pkgname, arch, indexes=[index_path])

    # Compare version (return when equal)
    compare = pmb.parse.version.compare(apkbuild_version, package.version)

    # APKBUILD > binary: this is fine
    if compare == 1:
        logging.info(
            f"NOTE: {pkgname} {arch} binary package has a lower"
            f" version {package.version} than the APKBUILD"
            f" {apkbuild_version}"
        )
        return aport_path

    # APKBUILD < binary: aports.git is outdated
    if compare == -1:
        logging.warning(
            "WARNING: Package '" + pkgname + "' has a lower version in"
            " local checkout of Alpine's aports ("
            + apkbuild_version
            + ") compared to Alpine's binary package ("
            + package.version
            + ")!"
        )
        logging.info("NOTE: You can update your local checkout with: 'pmbootstrap pull'")

    return aport_path


def prepare_tempdir() -> Path:
    """
    Prepare a temporary directory to do aportgen-related operations within.

    :returns: Path to a temporary directory for aportgen to work within.
    """
    # Prepare aportgen tempdir inside and outside of chroot
    chroot = Chroot.native()
    pmb.chroot.init(chroot)
    tempdir = Path("/tmp/aportgen")
    aportgen = get_context().config.work / "aportgen"
    pmb.chroot.root(["rm", "-rf", tempdir], chroot)
    pmb.helpers.run.user(["mkdir", "-p", aportgen, chroot / tempdir])

    return tempdir


def generate_checksums(tempdir: Path, apkbuild_path: Path) -> None:
    """
    Generate new checksums for a given APKBUILD.

    :param tempdir: Temporary directory as provided by prepare_tempdir().
    :param apkbuild_path: APKBUILD to generate new checksums for.
    """
    aportgen = get_context().config.work / "aportgen"

    pmb.build.init_abuild_minimal()
    pmb.chroot.root(["chown", "-R", "pmos:pmos", tempdir])
    pmb.chroot.user(["abuild", "checksum"], working_dir=tempdir)
    pmb.helpers.run.user(["cp", apkbuild_path, aportgen])
