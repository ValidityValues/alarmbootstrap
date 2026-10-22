# Copyright 2024 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import configparser
import os
import re
from enum import Enum
from glob import glob
from pathlib import Path
from typing import Final, TypedDict
from urllib.parse import urlparse

import pmb.config
import pmb.helpers.run
from pmb.core.context import get_context
from pmb.core.pkgrepo import pkgrepo_default_path, pkgrepo_name, pkgrepo_path
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError
from pmb.meta import Cache
from pmb.types import PathString, RunOutputTypeDefault

re_branch_aports = re.compile(r"^\d+\.\d\d+-stable$")
re_branch_pmaports = re.compile(r"^v\d\d\.\d\d$")


def get_path(name_repo: str) -> Path:
    """
    Get the path to the repository.

    The path is either the default one in the work dir, or a user-specified one in args.

    :returns: full path to repository
    """
    if name_repo == "aports_upstream":
        return get_context().config.work / "cache_git" / name_repo
    return pkgrepo_path(name_repo)


def clone(name_repo: str, do_shallow_clone: bool = False) -> None:
    """
    Clone a git repository to $WORK/cache_git/$name_repo.

    (or to the overridden path set in args, as with ``pmbootstrap --aports``).

    :param name_repo: short alias used for the repository name, from pmb.config.git_repos
        (e.g. "aports_upstream", "pmaports")
    :param do_shallow_clone: Whether to do a shallow (--depth=1) clone of the given repository.
    """
    # Check for repo name in the config
    if name_repo not in pmb.config.git_repos:
        raise ValueError("No git repository configured for " + name_repo)

    path = get_path(name_repo)
    if not path.exists():
        # Build git command
        url = pmb.config.git_repos[name_repo][0]
        command = ["git", "clone"]
        if do_shallow_clone:
            command.append("--depth=1")
        command += [url, str(path)]

        # Create parent dir and clone
        logging.info(f"Clone git repository: {url}")
        (get_context().config.work / "cache_git").mkdir(exist_ok=True)
        pmb.helpers.run.user(command, output=RunOutputTypeDefault.STDOUT)

    # FETCH_HEAD does not exist after initial clone. Create it, so
    # is_outdated() can use it.
    fetch_head = path / ".git/FETCH_HEAD"
    if not fetch_head.exists():
        open(fetch_head, "w").close()


def rev_parse(
    path: Path, revision: str = "HEAD", extra_args: list[str] = [], silent: bool = False
) -> str:
    """
    Run "git rev-parse" in a specific repository dir.

    :param path: to the git repository
    :param extra_args: additional arguments for ``git rev-parse``. Pass
        ``--abbrev-ref`` to get the branch instead of the commit, if possible.
    :returns: commit string like "90cd0ad84d390897efdcf881c0315747a4f3a966"
        or (with ``--abbrev-ref``): the branch name, e.g. "main"
    """
    command = ["git", "rev-parse", *extra_args, revision]
    rev = pmb.helpers.run.user_output(
        command, path, output=RunOutputTypeDefault.NULL if silent else RunOutputTypeDefault.LOG
    )
    return rev.rstrip()


def can_fast_forward(path: Path, branch_upstream: str, branch: str = "HEAD") -> bool:
    command = ["git", "merge-base", "--is-ancestor", branch, branch_upstream]
    ret = pmb.helpers.run.user(command, path, check=False)
    if ret == 0:
        return True
    elif ret == 1:
        return False
    else:
        raise RuntimeError("Unexpected exit code from git: " + str(ret))


def clean_worktree(path: Path, silent: bool = False) -> bool:
    """Check if there are not any modified files in the git dir."""
    command = ["git", "status", "--porcelain"]
    return (
        pmb.helpers.run.user_output(
            command, path, output=RunOutputTypeDefault.NULL if silent else RunOutputTypeDefault.LOG
        )
        == ""
    )


def list_remotes(aports: Path) -> list[str]:
    command = ["git", "remote", "-v"]
    output = pmb.helpers.run.user_output(command, aports, output=RunOutputTypeDefault.NULL)
    return output.splitlines()


def remote_to_name_and_clean_url(remote_line: str) -> tuple[str, str]:
    remote_name, url_part = remote_line.split("\t", 1)

    if url_part.startswith("https://"):
        # GitLab CI adds an authentication segment to the URL, which needs to be removed to be able
        # to match against the expected URLs later.
        parsed = urlparse(url_part)
        clean_url = f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
    else:
        clean_url = url_part

    return (remote_name, clean_url)


def get_upstream_remote(aports: Path) -> str:
    """
    Find the remote, which matches the git URL from the config.

    Usually "origin", but the user may have set up their git repository differently.
    """
    name_repo = pkgrepo_name(aports)
    if name_repo not in pmb.config.git_repos:
        logging.warning(f"WARNING: can't determine remote for {name_repo}, using 'origin'")
        return "origin"
    urls = pmb.config.git_repos[name_repo]
    lines = list_remotes(aports)
    for line in lines:
        remote_name, clean_url = remote_to_name_and_clean_url(line)

        if any(u.lower() in clean_url.lower() for u in urls):
            return remote_name

    # Fallback to old URLs, in case the migration was not done yet
    if name_repo == "pmaports":
        urls_outdated = OUTDATED_GIT_REMOTES_HTTP + OUTDATED_GIT_REMOTES_SSH
        for line in lines:
            if any(u in line.lower() for u in urls_outdated):
                logging.warning("WARNING: pmaports has an outdated remote URL")
                return line.split("\t", 1)[0]

    raise RuntimeError(
        f"{name_repo}: could not find remote name for any URL '{urls}' in git repository: {aports}"
    )


class RemoteType(Enum):
    FETCH = "fetch"
    PUSH = "push"

    @staticmethod
    def from_git_output(git_remote_type: str) -> "RemoteType":
        match git_remote_type:
            case "(fetch)":
                return RemoteType.FETCH
            case "(push)":
                return RemoteType.PUSH
            case _:
                raise ValueError(f'Unknown remote type "{git_remote_type}"')


def set_remote_url(repo: Path, remote_name: str, remote_url: str, remote_type: RemoteType) -> None:
    command: list[PathString] = [
        "git",
        "-C",
        repo,
        "remote",
        "set-url",
        remote_name,
        remote_url,
        "--push" if remote_type == RemoteType.PUSH else "--no-push",
    ]

    pmb.helpers.run.user(command, output=RunOutputTypeDefault.STDOUT)


# Intentionally lower case for case-insensitive comparison
OUTDATED_GIT_REMOTES_HTTP: Final[list[str]] = ["https://gitlab.com/postmarketos/pmaports.git"]
OUTDATED_GIT_REMOTES_SSH: Final[list[str]] = ["git@gitlab.com:postmarketos/pmaports.git"]


def migrate_upstream_remote() -> None:
    """Migrate pmaports git remote URL from gitlab.com to gitlab.postmarketos.org."""
    repo = pkgrepo_default_path()
    repo_name = repo.parts[-1]
    lines = list_remotes(repo)

    current_git_remote_http: Final[str] = pmb.config.git_repos[repo_name][0]
    current_git_remote_ssh: Final[str] = pmb.config.git_repos[repo_name][1]

    for line in lines:
        if not line:
            continue  # Skip empty line at the end.

        remote_name, remote_url, remote_type_raw = line.split()
        remote_type = RemoteType.from_git_output(remote_type_raw)

        if remote_url.lower() in OUTDATED_GIT_REMOTES_HTTP:
            new_remote = current_git_remote_http
        elif remote_url.lower() in OUTDATED_GIT_REMOTES_SSH:
            new_remote = current_git_remote_ssh
        else:
            new_remote = None

        if new_remote:
            logging.info(
                f"Migrating to new {remote_type.value} URL (from {remote_url} to {new_remote})"
            )
            set_remote_url(repo, remote_name, current_git_remote_http, remote_type)


class ChannelInfo(TypedDict):
    description: str
    branch_pmaports: str
    branch_aports: str
    mirrordir_alpine: str


class ChannelsCfg(TypedDict):
    meta: dict[str, str]
    channels: dict[str, ChannelInfo]


@Cache("aports")
def parse_channels_cfg(aports: Path) -> ChannelsCfg:
    """
    Parse channels.cfg from pmaports.git, origin/main branch.

    Reference: https://postmarketos.org/channels.cfg

    :returns: dict like: {"meta": {"recommended": "edge"},
        "channels": {"edge": {"description": ...,
        "branch_pmaports": ...,
        "branch_aports": ...,
        "mirrordir_alpine": ...},
        ...}}
    """
    # Read with configparser
    cfg = configparser.ConfigParser()
    override = os.environ.get("PMB_CHANNELS_CFG")

    if override:
        if not os.path.exists(override):
            raise NonBugError(f"Override from PMB_CHANNELS_CFG not found: {override}")
        try:
            cfg.read(override)
        except configparser.MissingSectionHeaderError as exception:
            raise RuntimeError(
                f"Failed to read channels.cfg from '{override}' (as set in environment by PMB_CHANNELS_CFG)"
            ) from exception
    else:
        remote = get_upstream_remote(aports)
        command = ["git", "show", f"{remote}/main:channels.cfg"]
        stdout = pmb.helpers.run.user_output(
            command, aports, output=RunOutputTypeDefault.NULL, check=False
        )
        try:
            cfg.read_string(stdout)
        except configparser.MissingSectionHeaderError as exception:
            logging.info(
                "NOTE: fix this by fetching your pmaports.git, e.g. with 'pmbootstrap pull'"
            )
            raise RuntimeError(
                f"Failed to read channels.cfg from '{remote}/main' branch of your local pmaports clone"
            ) from exception

    # Meta section
    ret: ChannelsCfg = {
        "channels": {},
        "meta": {"recommended": cfg.get("channels.cfg", "recommended")},
    }

    # Channels
    for channel in cfg.sections():
        if channel == "channels.cfg":
            continue  # meta section

        ret["channels"][channel] = ChannelInfo(
            description=cfg.get(channel, "description"),
            branch_pmaports=cfg.get(channel, "branch_pmaports"),
            branch_aports=cfg.get(channel, "branch_aports"),
            mirrordir_alpine=cfg.get(channel, "mirrordir_alpine"),
        )

    return ret


def branch_looks_official(repo: Path, branch: str) -> bool:
    """
    Check if a given branch follows the patterns of official branches in
       pmaports or aports.

    :returns: True if it looks official, False otherwise
    """
    if branch == "main" or branch == "master":
        return True
    if repo.parts[-1] == "pmaports":
        if re_branch_pmaports.match(branch):
            return True
    else:
        if re_branch_aports.match(branch):
            return True
    return False


def pull(repo_name: str) -> int:
    """
    Check if on official branch and essentially try ``git pull --ff-only``.

    Instead of really doing ``git pull --ff-only``, do it in multiple steps
    (``fetch, merge --ff-only``), so we can display useful messages depending
    on which part fails.

    :returns: integer, >= 0 on success, < 0 on error
    """
    repo = get_path(repo_name)

    # Skip if repo wasn't cloned
    if not os.path.exists(repo):
        logging.debug(repo_name + ": repo was not cloned, skipping pull!")
        return 1

    # Skip if not on official branch
    branch = rev_parse(repo, extra_args=["--abbrev-ref"])
    msg_start = f"{repo_name} (branch: {branch}):"
    if not branch_looks_official(repo, branch):
        if repo.parts[-1] == "pmaports":
            official_looking_branches = "main, v24.06, …"
        else:
            official_looking_branches = "master, 3.20-stable, …"
        logging.warning(
            f"{msg_start} not on one of the official branches"
            f" ({official_looking_branches}), skipping pull!"
        )
        return -1

    # Skip if workdir is not clean
    if not clean_worktree(repo):
        logging.warning(msg_start + " workdir is not clean, skipping pull!")
        return -2

    # Skip if branch is tracking different remote
    branch_upstream = get_upstream_remote(repo) + "/" + branch
    remote_ref = rev_parse(repo, branch + "@{u}", ["--abbrev-ref"])
    if remote_ref != branch_upstream:
        logging.warning(
            f"{msg_start} is tracking unexpected remote branch '{remote_ref}' instead"
            f" of '{branch_upstream}'"
        )
        return -3

    # Fetch (exception on failure, meaning connection to server broke)
    logging.info(msg_start + " git pull --ff-only")
    if not get_context().offline:
        pmb.helpers.run.user(["git", "fetch"], repo)

    # Skip if already up to date
    if rev_parse(repo, branch) == rev_parse(repo, branch_upstream):
        logging.info(msg_start + " already up to date")
        return 2

    # Skip if we can't fast-forward
    if not can_fast_forward(repo, branch_upstream):
        logging.warning(
            f"{msg_start} can't fast-forward to {branch_upstream}, looks like you changed"
            " the git history of your local branch. Skipping pull!"
        )
        return -4

    # Fast-forward now (should not fail due to checks above, so it's fine to
    # throw an exception on error)
    command = ["git", "merge", "--ff-only", branch_upstream]
    pmb.helpers.run.user(command, repo, RunOutputTypeDefault.STDOUT)
    return 0


def get_topdir(repo: Path) -> Path:
    """
    Get top-dir of git repo.

    :returns: the top dir of the git repository
    """
    res = pmb.helpers.run.user(
        ["git", "rev-parse", "--show-toplevel"], repo, output_return=True, check=False
    )
    return Path(res.strip())


def get_files(repo: Path, include_dot_git_dir: bool = False) -> list[str]:
    """
    Get all files inside a git repository, that are either already in the git tree or are not in gitignore.

    Do not list deleted files. To be used for creating a tarball of the git repository.

    :param path: top dir of the git repository
    :param include_dot_git_dir: Also include .git

    :returns: all files in a git repository as list, relative to path
    """
    ret = []
    files = pmb.helpers.run.user_output(["git", "ls-files"], repo).split("\n")
    files += pmb.helpers.run.user_output(
        ["git", "ls-files", "--exclude-standard", "--other"], repo
    ).split("\n")
    if include_dot_git_dir:
        files += glob("./.git/**/*", root_dir=repo, recursive=True)
    for file in files:
        if os.path.exists(f"{repo}/{file}"):
            ret += [file]

    return ret


def get_changed_files() -> set[Path]:
    """Get all changed files.

    Provides a set of all file paths that have uncommitted changes—both staged
    and unstaged—in the default package repository's git repository (usually
    pmaports).

    :returns: Set of changed file paths.
    """
    # Changed files
    ret = set()
    for file_string in pmb.helpers.run.user_output(
        # Diff against HEAD so we get both staged and unstaged changes.
        ["git", "diff", "--name-only", "HEAD"],
        working_dir=pkgrepo_default_path(),
    ).splitlines():
        file = Path(file_string)

        if (pkgrepo_default_path() / file).exists():
            ret.add(file)
    return ret


def _is_path_hidden(maybe_hidden: Path) -> bool:
    """Check whether a path would be considered hidden on Unix systems.

    Attempts to determine whether a path would be considered hidden on a Unix
    system.

    :param maybe_hidden: Path to analyse.
    :returns: True if the path is to be considered hidden, False otherwise.
    """
    return any(part[0] == "." for part in maybe_hidden.parts)


def get_changed_packages() -> set[str]:
    """Get all changed packages.

    Provides a set of the names of all packages that have uncommitted
    changes—both staged and unstaged—in the default package repository's git
    repository (usually pmaports).

    :returns: Set of the names of changed packages.
    """
    ret = set()
    for file in get_changed_files():
        # Skip files:
        # * in the root dir of pmaports (i.e. files with only one parent like ./README.md, which
        #   has the parent ".")
        # * path with a dot (e.g. .ci/, device/.shared-patches/)
        if len(file.parents) < 2 or _is_path_hidden(file):
            continue

        dirname = file.parent
        if file.name != "APKBUILD":
            # Walk up directories until we (eventually) find the package
            # the file belongs to (could be in a subdirectory of a package)
            while (
                dirname != dirname.parent
                and not (pkgrepo_default_path() / dirname / "APKBUILD").exists()
            ):
                dirname = dirname.parent

            # Unable to find APKBUILD the file belong to
            if dirname == dirname.parent:
                # ... maybe the package was deleted entirely?
                if not (pkgrepo_default_path() / file).exists():
                    continue

                # Weird, file does not belong to any package?
                continue
        elif not (pkgrepo_default_path() / file).exists():
            continue  # APKBUILD was deleted

        ret.add(dirname.name)

    return ret
