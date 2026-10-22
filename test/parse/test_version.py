# Copyright 2024 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later
from pmb.parse.version import Token, check_string, compare, get_token, parse_suffix, validate


def test_check_string() -> None:
    assert check_string("3.4.1", ">=1.0.0")
    assert not check_string("3.4.1", "<1.0.0")


def test_compare() -> None:
    assert compare("1", "1") == 0
    assert compare("9999", "9999") == 0
    assert compare("2024.01_rc99", "2024.01_rc99") == 0
    assert compare("9999.1", "9999") == 1
    assert compare("1.2.0", "1.1.99") == 1
    assert compare("9999_alpha1", "9999") == -1
    assert compare("2024.01_rc4", "2024.01_rc5") == -1


def test_get_token() -> None:
    next, value, rest = get_token(Token.LETTER, "2024.01_rc4")
    assert next == Token.DIGIT
    assert value == 50
    assert rest == "024.01_rc4"


def test_parse_suffix() -> None:
    rest, value, invalid_suffix = parse_suffix("alpha2")
    assert rest == "2"
    assert value == -4
    assert not invalid_suffix

    rest, value, invalid_suffix = parse_suffix("sigma2")
    assert rest == "sigma2"
    assert value == 0
    assert invalid_suffix


def test_validate() -> None:
    # Valid versions
    assert validate("1")
    assert validate("1.0")
    assert validate("1.0.0")
    assert validate("1.0.0_alpha1")
    assert validate("1.0.0_beta1")

    assert validate("9999")
    assert validate("25.0.45")
    assert validate("9999.22.1_alpha9")
    assert validate("2024.01_rc4")

    # Invalid versions
    assert not validate("1 . 2")
    assert not validate("abc")
    assert not validate("1.2.3_sigma4")
    assert not validate("Åland")
    assert not validate("9999999999.hello")
