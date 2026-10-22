# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import configparser
import os
from pathlib import Path, PosixPath

from pmb.core import Config
from pmb.helpers import logging


def load(path: Path) -> Config:
    config = Config()

    cfg = configparser.ConfigParser()
    if os.path.isfile(path):
        cfg.read(path)

    if "pmbootstrap" not in cfg:
        cfg["pmbootstrap"] = {}
    if "providers" not in cfg:
        cfg["providers"] = {}

    for key in Config.__dict__:
        if key == "providers":
            setattr(config, key, cfg["providers"])
        if key == "mirrors" and key in cfg:
            for subkey in Config.mirrors:
                if subkey in cfg["mirrors"]:
                    setattr(config, f"mirrors.{subkey}", cfg["mirrors"][subkey])
        # default values won't be set in the config file
        if key not in cfg["pmbootstrap"]:
            continue
        # Convert strings to paths
        elif type(getattr(Config, key)) is PosixPath:
            setattr(config, key, Path(cfg["pmbootstrap"][key]))
        # Yeah this really sucks and there isn't a better way to do it without external
        # libraries
        elif isinstance(getattr(Config, key), list) and isinstance(
            getattr(Config, key)[0], PosixPath
        ):
            value = cfg["pmbootstrap"][key]
            if not value:
                setattr(config, key, value)
            else:
                setattr(config, key, [Path(p) for p in value.split(",")])
        elif isinstance(getattr(Config, key), bool):
            setattr(config, key, cfg["pmbootstrap"][key].lower() == "true")
        elif key in cfg["pmbootstrap"]:
            setattr(config, key, cfg["pmbootstrap"][key])

    return config


def serialize(config: Config, skip_defaults: bool = True) -> configparser.ConfigParser:
    """
    Serialize the config object into a ConfigParser to write it out
    in the pmbootstrap_v3.cfg INI format.

    :param config: The config object to serialize
    :param skip_defaults: Skip writing out default values
    """
    cfg = configparser.ConfigParser()
    cfg["pmbootstrap"] = {}
    cfg["providers"] = {}
    cfg["mirrors"] = {}

    # .keys() flat maps dictionaries like config.mirrors with
    # dotted notation
    for key in Config.keys():  # ruff:ignore[in-dict-keys]
        # If the default value hasn't changed then don't write out,
        # this makes it possible to update the default, otherwise
        # we wouldn't be able to tell if the user overwrote it.
        if skip_defaults and Config.get_default(key) == getattr(config, key):
            continue
        if key == "providers":
            cfg["providers"] = config.providers
        elif key.startswith("mirrors."):
            key_ = key.split(".")[1]
            cfg["mirrors"][key_] = getattr(config, key)
        # Convert strings to paths
        elif type(getattr(Config, key)) is PosixPath:
            cfg["pmbootstrap"][key] = str(getattr(config, key))
        elif isinstance(getattr(Config, key), list) and isinstance(
            getattr(Config, key)[0], PosixPath
        ):
            cfg["pmbootstrap"][key] = ",".join(os.fspath(p) for p in getattr(config, key))
        elif isinstance(getattr(Config, key), bool):
            cfg["pmbootstrap"][key] = str(getattr(config, key))
        else:
            cfg["pmbootstrap"][key] = str(getattr(config, key))

    return cfg


# FIXME: we should have distinct Config and ConfigFile types
def save(output: Path, config: Config) -> None:
    """
    Save the config object to the specified path.

    IMPORTANT: The global config (available via get_context().config)
    has invocation arguments merged into it. Do NOT call save() with
    the global config object.
    """
    logging.debug(f"Save config: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.touch(0o600, exist_ok=True)

    cfg = serialize(config)

    with output.open("w") as handle:
        cfg.write(handle)
