# Copyright 2025 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

from pmb.helpers.other import normalize_hostname, validate_hostname


def test_normalize_hostname() -> None:
    # Fine as-is.
    assert normalize_hostname("a" * 63) == "a" * 63
    assert normalize_hostname("big-dipper") == "big-dipper"
    assert normalize_hostname("pumpkin") == "pumpkin"

    # Need changes.
    assert normalize_hostname("a" * 64) == "a" * 63
    assert normalize_hostname("big_dipper") == "big-dipper"


def test_validate_hostname() -> None:
    # Valid.
    assert validate_hostname("a" * 63)
    assert validate_hostname("hamburger")
    assert validate_hostname("123xyz")

    # Invalid.
    assert not validate_hostname("a" * 64)
    assert not validate_hostname(".hello")
    assert not validate_hostname("sign.")
    assert not validate_hostname(".house.")
    assert not validate_hostname("-turnip")
    assert not validate_hostname("blueberry-")
    assert not validate_hostname("-lamppost-")
    assert not validate_hostname("$$$")
    assert not validate_hostname("€")
    assert not validate_hostname("")
