# Copyright 2025 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from pmb.helpers.git import _is_path_hidden, branch_looks_official, remote_to_name_and_clean_url


def test_branch_looks_official() -> None:
    assert branch_looks_official(Path("Code/pmaports"), "main")
    # Old checkouts of pmaports may still be set to the "master" branch, and we need to allow
    # pulling from it for pmbootstrap to automatically switch to "main".
    assert branch_looks_official(Path("Code/pmaports"), "master")
    assert branch_looks_official(Path("Code/pmaports"), "v26.06")
    assert branch_looks_official(
        Path("/home/codemaster3000/.local/var/pmbootstrap/cache_git/pmaports"), "v26.06"
    )
    assert not branch_looks_official(Path("Code/pmaports"), "newbyte/cloudberry-eating-machine")
    assert not branch_looks_official(Path("Code/pmaports"), "3.19-stable")

    # Alpine aports still uses "master" as its development branch.
    assert branch_looks_official(Path("Code/aports"), "master")
    assert branch_looks_official(Path("Code/aports"), "3.23-stable")
    assert not branch_looks_official(Path("Code/aports"), "OpenRClover67/gnome-99")
    assert not branch_looks_official(Path("Code/aports"), "v25.06")


def test_remote_to_clean_url() -> None:
    name_1 = "origin"
    name_2 = "newbyte"

    raw_http_remote = "origin	https://gitlab.postmarketos.org/postmarketOS/pmaports.git (fetch)"
    clean_http_remote = "https://gitlab.postmarketos.org/postmarketOS/pmaports.git (fetch)"

    assert remote_to_name_and_clean_url(raw_http_remote) == (name_1, clean_http_remote)

    raw_http_remote_with_token = "origin	https://gitlab-ci-token:QVy1PB7sTxfy4pqfZM1U@gitlab.postmarketos.org/postmarketOS/pmaports.git (fetch)"

    assert remote_to_name_and_clean_url(raw_http_remote_with_token) == (name_1, clean_http_remote)

    raw_git_remote = "newbyte	git@gitlab.postmarketos.org:postmarketOS/pmaports.git (fetch)"
    clean_git_remote = "git@gitlab.postmarketos.org:postmarketOS/pmaports.git (fetch)"

    assert remote_to_name_and_clean_url(raw_git_remote) == (name_2, clean_git_remote)


def test_is_path_hidden() -> None:
    assert _is_path_hidden(Path(".ci/coolfile.txt"))
    assert _is_path_hidden(Path(".well-known/funding-manifest-urls"))
    assert _is_path_hidden(Path(".some-new-folder/with/really/deep/nesting/yeah.txt"))
    assert _is_path_hidden(Path(".shellcheckrc"))
    assert _is_path_hidden(Path("device/.shared-patches/something.patch"))

    assert not _is_path_hidden(Path("device/community/device-samsung-m0/APKBUILD"))
    assert not _is_path_hidden(Path("main/hello-world/main.c"))
    assert not _is_path_hidden(Path("temp/akms/akms.trigger"))
    assert not _is_path_hidden(Path("docs/Makefile"))
    assert not _is_path_hidden(Path("extra-repos/systemd/systemd/wired.network"))
