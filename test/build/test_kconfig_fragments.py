# Copyright 2025 Clayton Craft
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from pmb.build.kconfig import _extract_config_diff, _parse_config_options, parse_fragment


def test_parse_fragment_tristate() -> None:
    content = """CONFIG_FOO=y
CONFIG_BAR=m
# CONFIG_BAZ is not set"""

    result = parse_fragment(content)
    assert result["FOO"] == "y"
    assert result["BAR"] == "m"
    assert result["BAZ"] == "n"


def test_parse_fragment_string() -> None:
    content = 'CONFIG_CMDLINE="console=ttyS0"'
    result = parse_fragment(content)
    assert result["CMDLINE"] == "console=ttyS0"


def test_parse_fragment_string_with_spaces() -> None:
    content = 'CONFIG_CMDLINE="init=/sbin/init quiet"'
    result = parse_fragment(content)
    assert result["CMDLINE"] == "init=/sbin/init quiet"


def test_parse_fragment_array() -> None:
    content = 'CONFIG_LIST="foo,bar,baz"'
    result = parse_fragment(content)
    assert result["LIST"] == ["foo", "bar", "baz"]


def test_parse_fragment_numeric() -> None:
    content = "CONFIG_TIMEOUT=42"
    result = parse_fragment(content)
    assert result["TIMEOUT"] == "42"


def test_parse_fragment_hex() -> None:
    content = "CONFIG_BASE=0x1000"
    result = parse_fragment(content)
    assert result["BASE"] == "0x1000"


def test_parse_fragment_ignores_comments() -> None:
    content = """# Comment line
CONFIG_ENABLED=y
# Another comment
# is not set this config is"""

    result = parse_fragment(content)
    assert len(result) == 1
    assert result["ENABLED"] == "y"


def test_parse_fragment_mixed() -> None:
    content = """# Device config
CONFIG_DRM=y
CONFIG_DRM_PANEL=m
# CONFIG_DRM_DEBUG is not set
CONFIG_DRM_NAME="msm"
CONFIG_DRM_FORMATS="rgb565,xrgb8888" """

    result = parse_fragment(content)
    assert result["DRM"] == "y"
    assert result["DRM_PANEL"] == "m"
    assert result["DRM_DEBUG"] == "n"
    assert result["DRM_NAME"] == "msm"
    assert result["DRM_FORMATS"] == ["rgb565", "xrgb8888"]


def test_parse_config_options() -> None:
    config = """CONFIG_A=y
CONFIG_B=m
CONFIG_C="value"
# CONFIG_D is not set"""

    opts = _parse_config_options(config)
    assert opts["CONFIG_A"] == "y"
    assert opts["CONFIG_B"] == "m"
    assert opts["CONFIG_C"] == '"value"'
    assert opts["CONFIG_D"] == "n"


def test_extract_config_diff_changed_tristate(tmp_path: Path) -> None:
    baseline = "CONFIG_MODULE=y\n"
    new = "CONFIG_MODULE=m\n"

    out = tmp_path / "test.config"
    _extract_config_diff(new, baseline, out)

    content = out.read_text()
    assert "CONFIG_MODULE=m" in content


def test_extract_config_diff_new_options(tmp_path: Path) -> None:
    baseline = "CONFIG_A=y\n"
    new = "CONFIG_A=y\nCONFIG_B=m\nCONFIG_C=y\n"

    out = tmp_path / "test.config"
    _extract_config_diff(new, baseline, out)

    content = out.read_text()
    assert "CONFIG_B=m" in content
    assert "CONFIG_C=y" in content
    assert content.count("CONFIG_A") == 0


def test_extract_config_diff_disabled_option(tmp_path: Path) -> None:
    baseline = "CONFIG_DEBUG=y\n"
    new = "# CONFIG_DEBUG is not set\n"

    out = tmp_path / "test.config"
    _extract_config_diff(new, baseline, out)

    content = out.read_text()
    assert "# CONFIG_DEBUG is not set" in content


def test_extract_config_diff_no_changes(tmp_path: Path) -> None:
    config = "CONFIG_A=y\nCONFIG_B=m\n"

    out = tmp_path / "test.config"
    _extract_config_diff(config, config, out)

    # File shouldn't be created when there are no changes
    assert not out.exists()
