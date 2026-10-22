# Copyright 2025 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Final

import pytest

from pmb.helpers.exceptions import NonBugError
from pmb.parse._apkbuild import archived, maintainers

TESTDIR: Final[Path] = Path(__file__).parent.parent / "data/tests"


def test_maintainer_comment_style() -> None:
    assert maintainers(TESTDIR / "APKBUILD.maintainer-comment-style") == [
        "Maximilian von Rizzberg <max.rizz@example.com>",
    ]


def test_maintainer_comment_style_co_maintainers() -> None:
    assert maintainers(TESTDIR / "APKBUILD.maintainer-comment-style-co-maintainers") == [
        "Snusmumriken <snusmumriken@example.com>",
        "Lilla My <lilla.my@example.com>",
        "Snorkfröken <snorkfroken@example.com>",
    ]


def test_maintaner_comment_style_too_many() -> None:
    with pytest.raises(NonBugError):
        maintainers(TESTDIR / "APKBUILD.maintainer-comment-style-too-many")


def test_maintainer_field_style() -> None:
    assert maintainers(TESTDIR / "APKBUILD.maintainer-field-style") == [
        "Fieldman <man.of.the.field@example.com>"
    ]


def test_maintainer_field_style_co_maintainers() -> None:
    assert maintainers(TESTDIR / "APKBUILD.maintainer-field-style-co-maintainers") == [
        "Snusmumriken <snusmumriken@example.com>",
        "Lilla My <lilla.my@example.com>",
        "Snorkfröken <snorkfroken@example.com>",
    ]


def test_maintainer_mixed_style_too_many() -> None:
    with pytest.raises(NonBugError):
        maintainers(TESTDIR / "APKBUILD.maintainer-mixed-style-too-many")


def test_archived() -> None:
    assert (
        archived(TESTDIR / "APKBUILD.archived")
        == "I am tired of maintaining so many hello world programs!!"
    )
