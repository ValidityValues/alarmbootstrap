# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch
from _pytest.tmpdir import TempPathFactory

import pmb.core
from pmb.core.apkindex import Apkindex
from pmb.core.arch import Arch
from pmb.core.context import Context, get_context
from pmb.helpers.args import init as init_args
from pmb.types import PmbArgs

_testdir = Path(__file__).parent / "data/tests"


# request can be specified using parameterize from test cases
# e.g. @pytest.mark.parametrize("config_file", ["no-repos"], indirect=True)
# will set request.param to "no-repos"
@pytest.fixture
def config_file(tmp_path_factory: TempPathFactory, request: FixtureRequest) -> Path:
    """Fixture to create a temporary pmbootstrap_v3.cfg file."""
    tmp_path = tmp_path_factory.mktemp("pmbootstrap")

    flavour = "default"
    if hasattr(request, "param") and request.param:
        flavour = request.param

    out_file = tmp_path / "pmbootstrap_v3.cfg"
    workdir = tmp_path / "work"
    workdir.mkdir()

    configs = {"default": f"aports = {workdir / 'cache_git' / 'pmaports'}", "no-repos": "aports = "}

    file = _testdir / "pmbootstrap_v3.cfg"
    print(f"CONFIG: {out_file}")
    cfg = configs[flavour]
    contents = file.read_text().format(workdir, cfg)

    out_file.write_text(contents)
    return out_file


@pytest.fixture
def device_package(config_file: Path) -> Path:
    """Fixture to create a temporary deviceinfo file."""
    mock_device = "qemu-amd64"
    pkgdir = config_file.parent / f"device-{mock_device}"
    pkgdir.mkdir()

    for file in ["APKBUILD", "deviceinfo"]:
        shutil.copy(_testdir / f"{file}.{mock_device}", pkgdir / file)

    return pkgdir


@pytest.fixture(autouse=True)
def find_required_programs() -> None:
    """Fixture to find required programs for pmbootstrap."""
    pmb.config.require_programs()


@pytest.fixture
def mock_devices_find_path(device_package: Path, monkeypatch: MonkeyPatch) -> None:
    """Fixture to mock pmb.helpers.devices.find_path()"""

    def mock_find_path(codename: str, file: str = "") -> Path | None:
        print(f"mock_find_path({codename}, {file})")
        out = device_package / file
        if not out.exists():
            return None

        return out

    monkeypatch.setattr("pmb.helpers.devices.find_path", mock_find_path)


@pytest.fixture(autouse=True)
def logfile(tmp_path_factory: TempPathFactory) -> Path:
    """Setup logging for all tests."""
    from pmb.helpers import logging

    tmp_path = tmp_path_factory.getbasetemp()
    logfile = tmp_path / "log_testsuite.txt"
    logging.init(logfile, verbose=True)

    return logfile


@pytest.fixture(autouse=True)
def setup_mock_ask(monkeypatch: MonkeyPatch) -> None:
    """Common setup to mock cli.ask() to avoid reading from stdin"""
    import pmb.helpers.cli

    def mock_ask(
        question: str = "Continue?",
        choices: list[str] = ["y", "n"],
        default: str = "n",
        lowercase_answer: bool = True,
        validation_regex: None = None,
        complete: None = None,
    ) -> str:
        return default

    monkeypatch.setattr(pmb.helpers.cli, "ask", mock_ask)


# FIXME: get/set_context() is a bad hack :(
@pytest.fixture
def mock_context(monkeypatch: MonkeyPatch) -> None:
    """
    Mock set_context() to bypass sanity checks. Ideally we would
    mock get_context() as well, but since every submodule of pmb imports
    it like "from pmb.core.context import get_context()", we can't
    actually override it with monkeypatch.setattr(). So this is the
    best we can do... set_context() is only called from one place and is
    done so with the full namespace, so this works.
    """

    def mock_set_context(ctx: Context) -> None:
        print(f"mock_set_context({ctx})")
        setattr(pmb.core.context, "__context", ctx)

    monkeypatch.setattr("pmb.core.context.set_context", mock_set_context)


# FIXME: get_context() at runtime somehow doesn't return the
# custom context we set up here.
@pytest.fixture
def pmb_args(config_file: Path, mock_context: None, logfile: Path) -> None:
    """
    This is (still) a hack, since a bunch of the codebase still
    expects some global state to be initialised. We do that here.
    """
    args = PmbArgs()
    args.config = config_file
    args.aports = None
    args.timeout = 900
    args.details_to_stdout = False
    args.quiet = False
    args.verbose = True
    args.offline = False
    args.action = "init"
    args.cross = False
    args.ccache = True
    args.log = logfile

    init_args(args)

    print(f"WORK: {get_context().config.work}")

    # Sanity check
    assert ".pytest_tmp" in get_context().config.work.parts


@pytest.fixture
def foreign_arch() -> Arch:
    """Fixture to return the foreign arch."""
    if Arch.native() == Arch.x86_64:
        return Arch.aarch64

    return Arch.x86_64


@pytest.fixture
def pmaports(pmb_args: None, monkeypatch: MonkeyPatch) -> None:
    """Fixture to clone pmaports."""
    from pmb.core import Config
    from pmb.core.context import get_context

    cfg = get_context().config

    # As an optimisation, we check the default workdir for pmaports
    # and clone it from there if it exists. This saves a bunch of bandwidth
    # and time.
    if Config.aports.exists():
        # Override the URL to the local path so we can later look up the
        # remote by URL
        pmb.config.git_repos["pmaports"] = [str(Config.aports)]
    elif not os.environ.get("CI"):
        raise RuntimeError(f"Missing pmaports dir and not running in CI: {Config.aports}")

    if not cfg.aports.exists():
        pmb.helpers.git.clone("pmaports")
        # Now operate on the cloned repo
        assert pmb.helpers.run.user(["git", "switch", "main"], working_dir=cfg.aports) == 0


@pytest.fixture
def tmp_file(tmp_path: Path) -> Path:
    return Path(tempfile.mkstemp(dir=tmp_path)[1])


example_apkindex = """
C:Q1p+nGf5oBAmbU9FQvV4MhfEmWqVE=
P:postmarketos-base-ui-networkmanager
V:29-r1
A:aarch64
S:4185
I:5376
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:busctl dnsmasq-dnssec-dbus>=2.90-r1 gojq networkmanager networkmanager-cli networkmanager-tui networkmanager-wifi networkmanager-wwan networkmanager-dnsmasq

C:Q1j8i5C7tOHbhrd5OTtot1u1ZtteU=
P:postmarketos-base-ui-networkmanager-usb-tethering
V:29-r1
A:aarch64
S:3986
I:5206
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony dbus haveged nftables openssh-server-pam pipewire postmarketos-artwork-icons postmarketos-base shadow tzdata util-linux wireless-regdb wireplumber
i:postmarketos-base-ui-networkmanager=29-r1

C:Q10FDERw8SRwuk6ITfWNyJ4GbVE2I=
P:postmarketos-base-ui-openrc
V:29-r1
A:aarch64
S:1570
I:1
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony-openrc dbus-openrc haveged-openrc util-linux-openrc /bin/sh
i:postmarketos-base-ui=29-r1 openrc

C:Q1inMHA1+gsS8U50j8odasUNy5TVw=
P:postmarketos-base-ui-openrc-settingsd
V:29-r1
A:aarch64
S:1824
I:103
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony dbus haveged nftables openssh-server-pam pipewire postmarketos-artwork-icons postmarketos-base shadow tzdata util-linux wireless-regdb wireplumber /bin/sh
i:postmarketos-base-ui=29-r1 openrc-settingsd-openrc

C:Q1iB2PiTO0w29T4kRUSjqLOyKcCwY=
P:postmarketos-base-ui-qt-tweaks
V:29-r1
A:aarch64
S:1661
I:47
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony dbus haveged nftables openssh-server-pam pipewire postmarketos-artwork-icons postmarketos-base shadow tzdata util-linux wireless-regdb wireplumber

C:Q1aQ5UEOC902h2atx0fqDhahpkDY8=
P:postmarketos-base-ui-qt-wayland
V:29-r1
A:aarch64
S:1687
I:86
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony dbus haveged nftables openssh-server-pam pipewire postmarketos-artwork-icons postmarketos-base shadow tzdata util-linux wireless-regdb wireplumber

C:Q16q7k1Z5HAJe5qqeXfTIn62QQoBs=
P:postmarketos-base-ui-tinydm
V:29-r1
A:aarch64
S:2264
I:571
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony dbus haveged nftables openssh-server-pam pipewire postmarketos-artwork-icons postmarketos-base shadow tzdata util-linux wireless-regdb wireplumber
p:postmarketos-base-tinydm=29-r1
i:postmarketos-base-ui=29-r1 tinydm-openrc

C:Q11IrmIOlqZX5BzKhLsce+U+S+N3I=
P:postmarketos-base-ui-wayland
V:29-r1
A:aarch64
S:1361
I:0
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:chrony dbus haveged nftables openssh-server-pam pipewire postmarketos-artwork-icons postmarketos-base shadow tzdata util-linux wireless-regdb wireplumber
i:postmarketos-base-ui=29-r1 wayland-server-libs

C:Q1bDAQG9F9mi7Mi5CT3Csiq4QU52w=
P:postmarketos-base-ui-wifi-iwd
V:29-r1
A:aarch64
S:1650
I:26
T:Use iwd as the WiFi backend (but may not work with all devices)
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
k:90
D:iwd
p:postmarketos-base-ui-wifi=29-r1

C:Q1s7shLQ3sKNxKABRyQRBQ11RwkuU=
P:postmarketos-base-ui-wifi-iwd-openrc
V:29-r1
A:aarch64
S:1405
I:1
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:iwd-openrc openrc /bin/sh
i:postmarketos-base-ui-wifi-iwd=29-r1 openrc

C:Q1C23f0J5PBrNAuZiAhzCJhVpNe5c=
P:postmarketos-base-ui-wifi-wpa_supplicant
V:29-r1
A:aarch64
S:1262
I:0
T:Use wpa_supplicant as the WiFi backend.
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
k:100
D:wpa_supplicant
p:postmarketos-base-ui-wifi=29-r1

C:Q1LfWeOxxgIM3UE/QQBczMpJw17hY=
P:postmarketos-base-ui-wifi-wpa_supplicant-openrc
V:29-r1
A:aarch64
S:1691
I:37
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:wpa_supplicant-openrc openrc /bin/sh
i:postmarketos-base-ui-wifi-wpa_supplicant=29-r1 openrc

C:Q1yB3CVUFMOjnLOOEAUIUUpJJV8g0=
P:postmarketos-base-ui-x11
V:29-r1
A:aarch64
S:1587
I:22
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-ui
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:libinput xf86-input-libinput xf86-video-fbdev
p:postmarketos-base-x11=29-r1
i:postmarketos-base-ui=29-r1 xorg-server

C:Q1TgE1jgGt1PUb/Zwbi6rDRt3b8go=
P:postmarketos-initramfs
V:3.3.5-r2
A:aarch64
S:16530
I:143360
T:Base files for the postmarketOS initramfs / initramfs-extra
U:https://postmarketos.org
L:GPL-2.0-or-later
o:postmarketos-initramfs
m:Casey Connolly <kcxt@postmarketos.org>
t:1728049308
c:f3a4285732781d5577bad06046b7bbeaf132ce1f-dirty
k:10
D:blkid btrfs-progs buffyboard busybox-extras bzip2 cryptsetup device-mapper devicepkg-utils>=0.2.0 dosfstools e2fsprogs e2fsprogs-extra f2fs-tools font-terminus iskey kmod libinput-libs lz4 multipath-tools parted postmarketos-fde-unlocker postmarketos-mkinitfs>=2.2 udev unudhcpd util-linux-misc xz
p:postmarketos-ramdisk=3.3.5-r2"""


@pytest.fixture
def valid_apkindex_file(tmp_path: Path) -> Apkindex:
    # FIXME: use tmpfile fixture from !2453
    tmpfile = Apkindex(tmp_path / "APKINDEX.1")
    print(tmp_path)
    tmpfile.write_text(example_apkindex)

    return tmpfile
