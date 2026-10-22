# Copyright 2023 Mark Hargreaves, Luca Weiss
# SPDX-License-Identifier: GPL-3.0-or-later
import socket
import time
from pathlib import Path

import pmb.chroot
import pmb.helpers.run
from pmb.core import Chroot
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError


def start_nbd_server(device: str, replace: bool, ip: str = "172.16.42.2", port: int = 9999) -> None:
    """
    Start nbd server in chroot_native with pmOS rootfs.

    :param ip: IP address to serve nbd server for
    :param port: port of nbd server
    """
    chroot = Chroot.native()
    pmb.chroot.init(chroot)

    rootfs_path = Path("/mnt/pmbootstrap/netboot") / f"{device}.img"
    if not (chroot / rootfs_path).exists() or replace:
        rootfs_path2 = Path("/home/pmos/rootfs") / f"{device}.img"
        if not (chroot / rootfs_path2).exists():
            raise NonBugError(
                "The rootfs has not been generated yet, please run 'pmbootstrap install' first."
            )
        if replace and not pmb.helpers.cli.confirm(
            f"Are you sure you want to replace the rootfs for {device}?"
        ):
            return
        pmb.chroot.root(["cp", rootfs_path2, rootfs_path])
        logging.info(
            f"NOTE: Copied device image to {get_context().config.work}"
            f'/images_netboot/. The image will persist "pmbootstrap '
            f'zap" for your convenience. Use "pmbootstrap netboot '
            f'serve --help" for more options.'
        )

    pmb.chroot.apk.install(["nbd"], chroot)

    logging.info(f"Running nbd server for {device} on {ip} port {port}.")

    while True:
        logging.info("Waiting for postmarketOS device to appear...")

        # Try to bind to the IP ourselves before handing it to nbd-servere
        # This is purely to improve the UX as nbd-server just quits when it
        # cannot bind to an IP address.
        test_socket = socket.socket()
        while True:
            try:
                test_socket.bind((ip, 9998))
            except OSError as e:
                if e.errno != 99:  # Cannot assign requested address
                    raise
                # Wait a bit before retrying
                time.sleep(0.5)
                continue
            test_socket.close()
            break

        logging.info("Found postmarketOS device, serving image...")
        pmb.chroot.root(
            ["nbd-server", f"{ip}@{port}", rootfs_path, "-d"], check=False, disable_timeout=True
        )
        logging.info("nbd-server quit. Connection lost?")
        # On a reboot nbd-server will quit, but the IP address sticks around
        # for a bit longer, so wait.
        time.sleep(5)


def netboot(action_netboot: str, do_replace: bool) -> None:
    if action_netboot == "serve":
        device = get_context().config.device
        start_nbd_server(device, do_replace)
