# Mirror Configuration

A typical postmarketOS installation has one Alpine Linux mirror configured as
well as one postmarketOS mirror. As Alpine's CDN mirror is used by default, it
should be suitable for most users. The postmarketOS mirror can be configured
interactively with `pmbootstrap init`, under "additional options".

Find the currently selected mirrors in the output of `pmbootstrap status`, as
well as in `/etc/apk/repositories` for initialized chroots and finished
installations.

## Advanced

Some advanced use cases are supported by configuring the mirrors directly,
either by running the non-interactive `pmbootstrap config` command or by editing
`pmbootstrap_v3.cfg`. Find the lists of mirrors at
[mirrors.alpinelinux.org](https://mirrors.alpinelinux.org) and
[mirrors.postmarketos.org](https://mirrors.postmarketos.org).

### Change the mirrors non-interactively

```sh
pmbootstrap config mirrors.alpine http://uk.alpinelinux.org/alpine/
pmbootstrap config mirrors.pmaports http://postmarketos.craftyguy.net/
pmbootstrap config mirrors.systemd http://postmarketos.craftyguy.net/extra-repos/systemd/
```

Reset to default works as with all config options:

```sh
pmbootstrap config -r mirrors.alpine
pmbootstrap config -r mirrors.pmaports
pmbootstrap config -r mirrors.systemd
```

### Disable the postmarketOS mirror

This is useful to test bootstrapping from pure Alpine:

```sh
pmbootstrap config mirrors.pmaports none
pmbootstrap config mirrors.systemd none
```

### Use `_custom` mirrors

For all repositories, it is possible to add `_custom` entries, for example
`pmaports_custom` in addition to `pmaports`. If these are set, then pmbootstrap
creates addition entries in front of the real mirrors in
`/etc/apk/repositories`. This is used by [BPO](https://build.postmarketos.org)
to build packages with a WIP repository enabled in addition to the final
repository, but could also be used if you have another custom repository that
you want to use in addition to the postmarketOS binary package repository.

```sh
pmbootstrap config mirrors.pmaports_custom http://custom-repository-here
pmbootstrap config mirrors.systemd_custom http://custom-repository-here/extra-repos/systemd
```

### Installing keys

`pmbootstrap install` will automatically use and install keys in
`$WORKDIR/config_apk_keys`. Any keys used to sign custom mirrors should be
placed here before running `pmbootstrap install`.

### Bootstrapping a repository for an additional architecture

See also the [Environment Variables](environment_variables.md) section
for a workaround when the APKINDEX is missing
(e.g., if the repository for the additional architecture isn’t ready yet):

```sh
PMB_APK_FORCE_MISSING_REPOSITORIES=1 pmbootstrap install
```
