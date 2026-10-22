# Copyright 2025 Pablo Correa Gomez
# SPDX-License-Identifier: GPL-3.0-or-later

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from pmb.core.pkgrepo import pkgrepo_default_path
from pmb.parse.kconfigcheck import sanity_check

TESTDIR: Final[Path] = Path(__file__).parent.parent / "data/tests"


@pytest.fixture
def copy_kconfigcheck_toml() -> Iterator[None]:
    pkgrepo_default_path().mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TESTDIR / "kconfigcheck.toml", pkgrepo_default_path() / "kconfigcheck.toml")

    yield

    (pkgrepo_default_path() / "kconfigcheck.toml").unlink()
    pkgrepo_default_path().rmdir()


def test_basic(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "aliases": {"community": ["category:default"]},
        "category:default": {">=0.0.0": {"all": {"CGROUPS": "y"}}},
    }
    sanity_check(toml)


def test_no_aliases(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "category:default": {">=0.0.0": {"all": {"CGROUPS": "y"}}},
    }
    with pytest.raises(RuntimeError) as no_aliases:
        sanity_check(toml)
    assert "missing [aliases] section" in str(no_aliases.value)


def test_missing_category(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "aliases": {"community": ["default"]},
        "default": {">=0.0.0": {"all": {"CGROUPS": "y"}}},
    }
    with pytest.raises(RuntimeError) as missing_category:
        sanity_check(toml)
    assert "all categories must start with 'category:'!" in str(missing_category.value)


def test_bad_arch(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "aliases": {"community": ["category:default"]},
        "category:default": {">=0.0.0": {"x86 x64_64": {"CGROUPS": "y"}}},
    }
    with pytest.raises(ValueError) as bad_arch:
        sanity_check(toml)
    assert "Invalid architecture: 'x64_64'" in str(bad_arch.value)


def test_missing_arch(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "aliases": {"community": ["category:default"]},
        "category:default": {">=0.0.0": {"all": {"NET": "y"}}},
        "category:containers": {">=0.0.0": {"CGROUPS": "y"}},
    }
    with pytest.raises(RuntimeError) as missing_arch:
        sanity_check(toml)
    assert "category:containers is missing architecture information" in str(missing_arch.value)


def test_multiple_categories(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "aliases": {"community": ["category:default"]},
        "category:default category:uefi": {">=0.0.0": {"all": {"CGROUPS": "y"}}},
    }
    sanity_check(toml)


def test_multiple_categories_missing_category(pmb_args: None, copy_kconfigcheck_toml: None) -> None:
    toml = {
        "aliases": {"community": ["category:default"]},
        "category:default uefi": {">=0.0.0": {"all": {"CGROUPS": "y"}}},
    }
    with pytest.raises(RuntimeError) as missing_category:
        sanity_check(toml)
    assert "unexpected section: category:default uefi" in str(missing_category.value)
