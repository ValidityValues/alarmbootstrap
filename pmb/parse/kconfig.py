# Copyright 2023 Attila Szollosi
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re
from pathlib import Path
from typing import Literal, overload

import pmb.helpers.pmaports
import pmb.parse
import pmb.parse.kconfigcheck
from pmb.core.apk_package import Apkbuild
from pmb.core.arch import Arch
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError


def is_set(config: str, option: str) -> bool:
    """
    Check, whether a boolean or tristate option is enabled
    either as builtin or module.

    :param config: full kernel config as string
    :param option: name of the option to check, e.g. EXT4_FS
    :returns: True if the check passed, False otherwise
    """
    return re.search("^CONFIG_" + option + "=[ym]$", config, re.MULTILINE) is not None


def is_set_str(config: str, option: str, string: str) -> bool:
    """
    Check, whether a config option contains a string as value.

    :param config: full kernel config as string
    :param option: name of the option to check, e.g. EXT4_FS
    :param string: the expected string
    :returns: True if the check passed, False otherwise
    """
    match = re.search("^CONFIG_" + option + "=(.*)$", config, re.MULTILINE)
    if match:
        return string == match.group(1).strip('"')
    else:
        return False


def is_in_array(config: str, option: str, string: str) -> bool:
    """
    Check, whether a config option contains string as an array element

    :param config: full kernel config as string
    :param option: name of the option to check, e.g. EXT4_FS
    :param string: the string expected to be an element of the array
    :returns: True if the check passed, False otherwise
    """
    match = re.search("^CONFIG_" + option + '="(.*)"$', config, re.MULTILINE)
    if match:
        values = match.group(1).split(",")
        return string in values
    else:
        return False


def check_option(
    component: str,
    details: bool,
    config: str,
    config_path: Path,
    option: str,
    option_value: bool | str | list[str],
) -> bool:
    """
    Check, whether one kernel config option has a given value.

    :param component: name of the component to test (postmarketOS, waydroid, …)
    :param details: print all warnings if True, otherwise one per component
    :param config: full kernel config as string
    :param config_path: full path to kernel config file
    :param option: name of the option to check, e.g. EXT4_FS
    :param option_value: expected value, e.g. True, "str", ["str1", "str2"]
    :returns: True if the check passed, False otherwise
    """

    def warn_ret_false(should_str: str) -> bool:
        config_name = os.path.basename(config_path)
        if details:
            logging.error(
                f"ERROR: {config_name}: CONFIG_{option} should {should_str} ({component})"
            )
        else:
            logging.warning(
                f"WARNING: {config_name} isn't configured properly"
                f" ({component}), run 'pmbootstrap kconfig check'"
                " for details!"
            )
        return False

    def warn_ret_true(should_str: str) -> bool:
        config_name = os.path.basename(config_path)
        if details:
            logging.warning(
                f"INFO: {config_name}: CONFIG_{option} is preferably {should_str} ({component})"
            )
        else:
            logging.warning(
                f"INFO: {config_name} has suboptimal configuration"
                f" ({component}), run 'pmbootstrap kconfig check'"
                " for details!"
            )
        return True

    if isinstance(option_value, list):
        for string in option_value:
            if not is_in_array(config, option, string):
                return warn_ret_false(f'contain "{string}"')
    elif isinstance(option_value, str):
        if option_value in ["y", "m", "n"]:
            # Tristate option
            if option_value == "n":
                if is_set(config, option):
                    return warn_ret_false("*not* be set")
                return True

            if not is_set(config, option):
                return warn_ret_false(f"be enabled and preferably set to '{option_value}'")

            # Store value to avoid a few extra calls to is_set_str
            if is_set_str(config, option, "y"):
                actual = "y"
            elif is_set_str(config, option, "m"):
                actual = "m"
            else:
                return warn_ret_false("be set to y or m (invalid tristate value)")

            if option_value != actual:
                warn_ret_true(f"{option_value}, but currently {actual}")
        else:
            # Regular string option
            if not is_set_str(config, option, option_value):
                return warn_ret_false(f'be set to "{option_value}"')
    elif option_value in [True, False]:
        if option_value != is_set(config, option):
            return warn_ret_false("be set" if option_value else "*not* be set")
    else:
        raise RuntimeError(
            "kconfig check code can only handle booleans,"
            f" strings and arrays. Given value {option_value}"
            " is not supported. If you need this, please patch"
            " pmbootstrap or open an issue."
        )
    return True


def check_config_options_set(
    config: str,
    config_path: Path,
    config_arch: Arch,
    options: dict[str, dict],
    component: str,
    pkgver: str,
    details: bool = False,
) -> bool:
    """
    Check, whether all the kernel config passes all rules of one component.

    Print a warning if any is missing.

    :param config: full kernel config as string
    :param config_path: full path to kernel config file
    :param config_arch: architecture name (alpine format, e.g. aarch64, x86_64)
    :param options: dictionary returned by pmb.parse.kconfigcheck.read_categories().
    :param component: name of the component to test (postmarketOS, waydroid, …)
    :param pkgver: kernel version
    :param details: print all warnings if True, otherwise one per component
    :returns: True if the check passed, False otherwise
    """
    ret = True
    for rules, archs_options in options.items():
        # Skip options irrelevant for the current kernel's version
        # Example rules: ">=4.0 <5.0"
        skip = False
        for rule in rules.split(" "):
            if not pmb.parse.version.check_string(pkgver, rule):
                skip = True
                break
        if skip:
            continue

        for archs, arch_options in archs_options.items():
            # If option does not contain the architecture of the device kernel,
            # then just skip the option
            if config_arch not in Arch.from_arch_field(archs.split()):
                continue

            for option, option_value in arch_options.items():
                if not check_option(component, details, config, config_path, option, option_value):
                    ret = False
                    # Stop after one non-detailed error
                    if not details:
                        return False
    return ret


def check_config(
    config_path: Path,
    config_arch: Arch,
    pkgver: str,
    categories: list[str],
    details: bool = False,
) -> bool:
    """
    Check, whether one kernel config passes the rules of multiple categories.

    :param config_path: full path to kernel config file
    :param config_arch: architecture name (alpine format, e.g. aarch64, x86_64)
    :param pkgver: kernel version
    :param categories: what to check for, e.g. ["waydroid", "iwd"]
    :param details: print all warnings if True, otherwise one per component
    :returns: True if the check passed, False otherwise
    """
    logging.debug(f"Check kconfig: {config_path}")
    config = config_path.read_text()

    if "default" not in categories:
        categories += ["default"]

    # Get all rules
    rules = pmb.parse.kconfigcheck.read_categories(categories)

    # Check the rules of each category
    ret = []
    for category in rules:
        ret += [
            check_config_options_set(
                config, config_path, config_arch, rules[category], category, pkgver, details
            )
        ]

    return all(ret)


@overload
def check(
    pkgname: str,
    categories: list[str] = ...,
    details: bool = ...,
    must_exist: Literal[False] = ...,
    architecture: Arch | None = None,
) -> bool | None: ...


@overload
def check(
    pkgname: str,
    categories: list[str] = ...,
    details: bool = ...,
    must_exist: Literal[True] = ...,
    architecture: Arch | None = None,
) -> bool: ...


def check(
    pkgname: str,
    categories: list[str] = [],
    details: bool = False,
    must_exist: bool = True,
    architecture: Arch | None = None,
) -> bool | None:
    """
    Check for necessary kernel config options in a package.

    :param pkgname: the package to check for, optionally without "linux-"
    :param categories: what to check for, e.g. ["waydroid", "iwd"]
    :param details: print all warnings if True, otherwise one generic warning
    :param must_exist: if False, just return if the package does not exist
    :param architecture: if not None, check only for the specified architecture
    :returns: True when the check was successful, False otherwise
              None if the aport cannot be found (only if must_exist=False)
    """
    # Don't modify the original list (arguments are passed as reference, a list
    # is not immutable)
    categories = categories.copy()

    # Pkgname: allow omitting "linux-" prefix
    flavor = pkgname.split("linux-")[1] if pkgname.startswith("linux-") else pkgname

    # Read all kernel configs in the aport
    ret = True
    aport: Path
    try:
        aport = pmb.helpers.pmaports.find("linux-" + flavor)
    except RuntimeError:
        if must_exist:
            raise
        return None
    apkbuild = pmb.parse.apkbuild(aport / "APKBUILD")
    pkgver = apkbuild["pkgver"]

    # Get categories from the APKBUILD
    for option in apkbuild["options"]:
        if not option.startswith("pmb:kconfigcheck-"):
            continue
        category = option.split("-", 1)[1]
        categories += [category]

    for config_path in aport.glob("config-*"):
        # The architecture of the config is in the name, so it just needs to be
        # extracted
        config_name = os.path.basename(config_path)
        config_name_split = config_name.split(".")

        if len(config_name_split) != 2:
            raise NonBugError(
                f"{config_name} is not a valid kernel config"
                "name. Ensure that the _config property in your "
                "kernel APKBUILD has a . before the "
                "architecture name, e.g. .aarch64 or .armv7, "
                "and that there is no excess punctuation "
                "elsewhere in the name."
            )

        config_arch = Arch.from_str(config_name_split[1])

        if architecture is not None and architecture != config_arch:
            continue

        ret &= check_config(
            config_path,
            config_arch,
            pkgver,
            categories,
            details=details,
        )
    return ret


def extract_arch(config_path: Path) -> Arch:
    # Extract the architecture out of the config
    config = config_path.read_text()
    if is_set(config, "ARM"):
        return Arch.armv7
    elif is_set(config, "ARM64"):
        return Arch.aarch64
    elif is_set(config, "RISCV"):
        return Arch.riscv64
    elif is_set(config, "X86_32"):
        return Arch.x86
    elif is_set(config, "X86_64"):
        return Arch.x86_64

    # No match
    raise NonBugError("failed to extract arch from kernel config, unsupported architecture?")


def extract_version(config_path: Path) -> str:
    # Try to extract the version string out of the comment header
    with open(config_path) as f:
        # Read the first 3 lines of the file and get the third line only
        text = [next(f) for x in range(3)][2]
    ver_match = re.match(r"# Linux/\S+ (\S+) Kernel Configuration", text)
    if ver_match:
        return ver_match.group(1).replace("-", "_")

    # No match
    logging.info("WARNING: failed to extract version from kernel config")
    return "unknown"


def check_file(config_path: Path, categories: list[str] = [], details: bool = False) -> bool:
    """
    Check for necessary kernel config options in a kconfig file.

    :param config_path: full path to kernel config file
    :param categories: what to check for, e.g. ["waydroid", "iwd"]
    :param details: print all warnings if True, otherwise one generic warning
    :returns: True when the check was successful, False otherwise
    """
    arch = extract_arch(config_path)
    version = extract_version(config_path)
    logging.debug(f"Check kconfig: parsed arch={arch}, version={version} from file: {config_path}")
    return check_config(config_path, arch, version, categories, details=details)


def create_fragment_from_rules(apkbuild: Apkbuild, rules: dict[str, dict], arch: Arch) -> str:
    """
    Given a set of kconfigcheck rules, generate a kconfig fragment for a specific architecture
    based on the version of the kernel package.

    :param apkbuild: parsed apkbuild for kernel package
    :param rules: kconfigcheck rules
    :param arch: target architecture
    :returns: kconfig fragment as a string
    """
    pkgver = apkbuild["pkgver"]

    fragment_lines: list[str] = []

    # Process each category
    for category_key, category_rules in rules.items():
        # Extract category name from "category:name" format
        category_name = " + ".join(cat.split(":", 1)[1] for cat in category_key.split())
        options_added = False

        # Check if this rule applies to kernel version
        for version_spec, arch_options in category_rules.items():
            applies = True
            for rule in version_spec.split(" "):
                if not pmb.parse.version.check_string(pkgver, rule):
                    applies = False
                    break

            if not applies:
                continue

            # Check if this rule applies to arch
            for arch_spec, options in arch_options.items():
                if arch_spec != "all" and str(arch) not in arch_spec.split(" "):
                    continue

                # Add category header comment
                if not options_added and options:
                    fragment_lines.append(f"# {category_name}")
                    options_added = True

                # Add each option
                for option, value in sorted(options.items()):
                    if isinstance(value, str):
                        if value in ["y", "m", "n"]:
                            # Tristate option
                            if value == "n":
                                fragment_lines.append(f"# CONFIG_{option} is not set")
                            else:
                                fragment_lines.append(f"CONFIG_{option}={value}")
                        else:
                            # Regular string option
                            fragment_lines.append(f'CONFIG_{option}="{value}"')
                    elif isinstance(value, list):
                        # For lists, join with commas
                        joined = ",".join(value)
                        fragment_lines.append(f'CONFIG_{option}="{joined}"')
                    elif isinstance(value, int):
                        fragment_lines.append(f"CONFIG_{option}={value}")
                    else:
                        logging.info(f"WARNING: value is of unknown type, ignoring: {value}")

        if options_added:
            # Padding between categories in fragment
            fragment_lines.append("")

    return "\n".join(fragment_lines)


def create_pmos_fragment(apkbuild: Apkbuild, arch: Arch) -> str:
    """
    Generate a kconfig fragment based on categories and version from a kernel's
    APKBUILD.

    :param apkbuild: parsed apkbuild for kernel package
    :param arch: target architecture
    :returns: kconfig fragment as a string
    """
    # Extract categories from APKBUILD options
    categories = ["default"]  # Always include default
    for option in apkbuild["options"]:
        if option.startswith("pmb:kconfigcheck-"):
            category = option.split("-", 1)[1]
            categories.append(category)

    # Collect all rules from the categories
    all_rules = pmb.parse.kconfigcheck.read_categories(categories)

    return create_fragment_from_rules(apkbuild, all_rules, arch)


def create_generic_fragment(apkbuild: Apkbuild, arch: Arch) -> str:
    """
    Generate a kconfig fragment for a generic kernel using options from
    kconfig-generic.toml.

    :param apkbuild: parsed apkbuild for kernel package
    :param arch: target architecture
    :returns: kconfig fragment as a string
    """
    # Collect rules from kconfig-generic.toml
    generic_rules = pmb.parse.kconfigcheck.get_generic_kconfig()

    return create_fragment_from_rules(apkbuild, generic_rules, arch)
