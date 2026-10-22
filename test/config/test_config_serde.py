# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pmb.config
from pmb.core.config import ServiceManagerConfig

"""Test the config file serialization and deserialization."""


def test_load(config_file: Path) -> None:
    config = pmb.config.load(config_file)
    assert config.build_default_device_arch
    assert config.ccache_size == "5G"
    assert config.device == "qemu-amd64"
    assert config.extra_packages == "neofetch,neovim,reboot-mode"
    assert config.hostname == "qemu-amd64"
    assert not config.is_default_channel
    assert config.jobs == 8
    assert config.kernel == "edge"
    assert config.locale == "C.UTF-8"
    assert config.ssh_keys
    assert config.sudo_timer
    assert config.service_manager == ServiceManagerConfig.SYSTEMD
    assert config.timezone == "Europe/Berlin"
    assert config.ui == "gnome"
    assert config.providers == {}
    assert config.mirrors["pmaports"]
    assert ".pytest_tmp" in config.work.parts
