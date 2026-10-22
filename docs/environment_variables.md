# Environment Variables

## `PMB_SUDO`

pmbootstrap supports `doas`, `sudo`, and `run0`. If multiple sudo
implementations are installed, pmbootstrap will use `doas`. You can set the
`PMB_SUDO` environmental variable to define the sudo implementation you want
to use.

## `PMB_APK_FORCE_MISSING_REPOSITORIES`

When this is set to `1`, pmbootstrap will not complain if downloading an
APKINDEX results in a 404 not found error. This is used by
[bpo](https://build.postmarketos.org) when building a new stable repository for
the first time. For example if the `x86_64` repository was already built and
published, but the `aarch64` repository wasn't published yet.
This is also the default behavior when building for architectures that are not
marked as supported in `pmaports.cfg`.

## `PMB_APK_NO_CACHE`

When this is set to `1`, pmbootstrap will disable apk's caching feature. This
is used by bpo for image build jobs, so these jobs don't need as much space.

## `PMB_CHANNELS_CFG`

Set this variable to the path of a copy of
[channels.cfg](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/blob/main/channels.cfg)
on disk to have pmbootstrap read it from there instead of `origin/main` from
pmaports. This is used by bpo with shallow clones of pmaports, where the main
branch may not be available (e.g. when building packages for a release branch).

## `PMB_FDE_PASSWORD`

This variable can be used to set the password when running `install --fde`. The
password is written to a temporary file and can be read from
`/proc/<pid>/environ`. Make sure you are aware of the security implications,
consider using this feature only with test passwords or in environments such as
live operating systems running in memory.

## `PMB_FILE_WAIT_UNTIL_EXISTS_MAX`

During installation, pmbootstrap creates partitions and uses partprobe to
inform the OS of partition table changes. Unfortunately the partition device
files do not appear instantly, and so we need to poll until the files exist.
pmbootstrap polls every 100 ms. This variable can be used to tweak the maximum
tries, the default is 150 (roughly 15s).
