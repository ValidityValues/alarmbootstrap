# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
from enum import IntEnum

"""
In order to stay as compatible to Alpine's apk as possible, this code
is heavily based on:

https://gitlab.alpinelinux.org/alpine/apk-tools/-/blob/5d796b567819ce91740fcdea7cbafecbda65d8f3/src/version.c
"""


class Token(IntEnum):
    """C equivalent: enum PARTS"""

    INVALID = -1
    DIGIT_OR_ZERO = 0
    DIGIT = 1
    LETTER = 2
    SUFFIX = 3
    SUFFIX_NO = 4
    REVISION_NO = 5
    END = 6


def next_token(previous: Token, rest: str) -> tuple[Token, str]:
    """
    Parse the next token in the rest of the version string, we're
    currently looking at.

    We do *not* get the value of the token, or advance the rest string
    beyond the whole token that is what the get_token() function does
    (see below).

    :param previous: the token before
    :param rest: of the version string
    :returns: (next, rest) next is the upcoming token, rest is the
              input "rest" string with one leading '.', '_' or '-'
              character removed (if there was any).

    C equivalent: next_token()
    """
    next = Token.INVALID
    char = rest[:1]

    # Tokes, which do not change rest
    if not len(rest):
        next = Token.END
    elif previous in [Token.DIGIT, Token.DIGIT_OR_ZERO] and char.islower():
        next = Token.LETTER
    elif previous == Token.LETTER and char.isdigit():
        next = Token.DIGIT
    elif previous == Token.SUFFIX and char.isdigit():
        next = Token.SUFFIX_NO

    # Tokens, which remove the first character of rest
    else:
        if char == ".":
            next = Token.DIGIT_OR_ZERO
        elif char == "_":
            next = Token.SUFFIX
        elif rest.startswith("-r"):
            next = Token.REVISION_NO
            rest = rest[1:]
        elif char == "-":
            next = Token.INVALID
        rest = rest[1:]

    # Validate current token
    # Check if the transition from previous to current is valid
    if next < previous and not (
        (next == Token.DIGIT_OR_ZERO and previous == Token.DIGIT)
        or (next == Token.SUFFIX and previous == Token.SUFFIX_NO)
        or (next == Token.DIGIT and previous == Token.LETTER)
    ):
        next = Token.INVALID
    return (next, rest)


def parse_suffix(rest: str) -> tuple[str, int, bool]:
    """
    Cut off the suffix of rest (which is now at the beginning of the
    rest variable, but regarding the whole version string, it is a
    suffix), and return a value integer (so it can be compared later,
    "beta" > "alpha" etc).

    :param rest: what is left of the version string that we are
                 currently parsing, starts with a "suffix" value
                 (see below for valid suffixes).
    :returns: (rest, value, invalid_suffix)
              - rest: is the input "rest" string without the suffix
              - value: is a signed integer (negative for pre-,
              positive for post-suffixes).
              - invalid_suffix: is true, when rest does not start
              with anything from the suffixes variable.

    C equivalent: get_token(), case TOKEN_SUFFIX
    """
    name_suffixes = collections.OrderedDict(
        [
            ("pre", ["alpha", "beta", "pre", "rc"]),
            ("post", ["cvs", "svn", "git", "hg", "p"]),
        ]
    )

    for name, suffixes in name_suffixes.items():
        for i, suffix in enumerate(suffixes):
            if not rest.startswith(suffix):
                continue
            rest = rest[len(suffix) :]
            value = i
            if name == "pre":
                value = value - len(suffixes)
            return (rest, value, False)
    return (rest, 0, True)


def get_token(previous: Token, rest: str) -> tuple[Token, int, str]:
    """
    This function does three things:
    * get the next token
    * get the token value
    * cut-off the whole token from rest

    :param previous: the token before
    :param rest: of the version string
    :returns: (next, value, rest) next is the new token string,
              value is an integer for comparing, rest is the rest of the
              input string.

    C equivalent: get_token()
    """
    # Set defaults
    value = 0
    next = Token.INVALID
    invalid_suffix = False

    # Bail out if at the end
    if not len(rest):
        return (Token.END, 0, rest)

    # Cut off leading zero digits
    if previous == Token.DIGIT_OR_ZERO and rest.startswith("0"):
        while rest.startswith("0"):
            rest = rest[1:]
            value -= 1
        next = Token.DIGIT

    # Add up numeric values
    elif previous in [Token.DIGIT_OR_ZERO, Token.DIGIT, Token.SUFFIX_NO, Token.REVISION_NO]:
        for i in range(len(rest)):
            while len(rest) and rest[0].isdigit():
                value *= 10
                value += int(rest[i])
                rest = rest[1:]

    # Append chars or parse suffix
    elif previous == Token.LETTER:
        value = ord(rest[0])
        rest = rest[1:]
    elif previous == Token.SUFFIX:
        (rest, value, invalid_suffix) = parse_suffix(rest)

    # Invalid previous token
    else:
        value = -1

    # Get the next token (for non-leading zeros)
    if not len(rest):
        next = Token.END
    elif next == Token.INVALID and not invalid_suffix:
        (next, rest) = next_token(previous, rest)

    return (next, value, rest)


def validate(version: str) -> bool:
    """
    Check whether one version string is valid.

    :param version: full version string
    :returns: True when the version string is valid

    C equivalent: apk_version_validate()
    """
    current = Token.DIGIT
    rest = version
    while current != Token.END:
        (current, _, rest) = get_token(current, rest)
        if current == Token.INVALID:
            return False
    return True


def compare(a_version: str, b_version: str, fuzzy: bool = False) -> int:
    """
    Compare two versions A and B to find out which one is higher, or if
    both are equal.

    :param a_version: full version string A
    :param b_version: full version string B
    :param fuzzy: treat version strings, which end in different token
                  types as equal

    :returns:
        (a <  b): -1
        (a == b):  0
        (a >  b):  1

    C equivalent: apk_version_compare_blob_fuzzy()
    """
    # Defaults
    a_token = Token.DIGIT
    b_token = Token.DIGIT
    a_value = 0
    b_value = 0
    a_rest = a_version
    b_rest = b_version

    # Parse A and B one token at a time, until one string ends, or the
    # current token has a different type/value
    while a_token == b_token and a_token not in [Token.END, Token.INVALID] and a_value == b_value:
        (a_token, a_value, a_rest) = get_token(a_token, a_rest)
        (b_token, b_value, b_rest) = get_token(b_token, b_rest)

    # Compare the values inside the last tokens
    if a_value < b_value:
        return -1
    if a_value > b_value:
        return 1

    # Equal: When tokens are the same strings, or when the value
    # is the same and fuzzy compare is enabled
    if a_token == b_token or fuzzy:
        return 0

    # Leading version components and their values are equal, now the
    # non-terminating version is greater unless it's a suffix
    # indicating pre-release
    if a_token == Token.SUFFIX:
        (a_token, a_value, a_rest) = get_token(a_token, a_rest)
        if a_value < 0:
            return -1
    if b_token == Token.SUFFIX:
        (b_token, b_value, b_rest) = get_token(b_token, b_rest)
        if b_value < 0:
            return 1

    # Compare the token value (e.g. digit < letter)
    if a_token > b_token:
        return -1
    if a_token < b_token:
        return 1

    # The tokens are not the same, but previous checks revealed that it
    # is equal anyway (e.g. "1.0" == "1").
    return 0


"""
Convenience functions below are not modeled after apk's version.c.
"""


def check_string(a_version: str, rule: str) -> bool:
    """
    Compare a version against a check string. This is used in "pmbootstrap
    kconfig check", to only require certain options if the pkgver is in a
    specified range (#1795).

    :param a_version: "3.4.1"
    :param rule: ">=1.0.0"
    :returns: True if a_version matches rule, false otherwise.

    """
    # Operators and the expected returns of compare(a,b)
    operator_results = {">=": [1, 0], "<": [-1]}

    # Find the operator
    b_version = None
    expected_results = None
    for operator in operator_results:
        if rule.startswith(operator):
            b_version = rule[len(operator) :]
            expected_results = operator_results[operator]
            break

    # No operator found
    if not b_version:
        raise RuntimeError(
            "Could not find operator in '" + rule + "'. You"
            " probably need to adjust check_string() in"
            " pmb/parse/version.py."
        )

    # Compare
    result = compare(a_version, b_version)
    return not expected_results or result in expected_results
