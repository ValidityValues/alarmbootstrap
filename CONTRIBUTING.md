# Contributing

pmbootstrap development is being discussed in
[#postmarketOS-devel](https://wiki.postmarketos.org/wiki/Matrix_and_IRC).

The usual [rules for
merging](https://wiki.postmarketos.org/wiki/Rules_for_merging) apply to this
repository.

## CI scripts

Use `pmbootstrap ci` inside your `pmbootstrap.git` dir, to run all CI scripts
locally.

## Coding style

A lot of the coding style is enforced by the CI scripts.

### Python

* Use [PEP8](https://www.python.org/dev/peps/pep-0008/).
* Max line length: 80-100 characters (use 80 for comments and most code lines
  except when 100 makes much more sense; try to keep it consistent with existing
  code).
* Use [f-strings](https://peps.python.org/pep-0498/) for any new or modified
  code, instead of any of the other string formatting methods.
* pmbootstrap should run on any Linux distribution, so we support [all active
  Python versions](https://www.python.org/downloads/).
* ruff is used to enforce a consistent code style, it is run in CI and can be
  easily run locally too (see Linting down below).
* Docstrings below functions are formatted in `reST` style:

```python
"""
This is a reST style.

:param param1: this is a first param
:param param2: this is a second param
:returns: this is a description of what is returned
:raises keyError: raises an exception
"""
```

#### Linting

To avoid having to fight with ruff in CI, it's recommended to enable a
pre-commit hook to run it automatically before you commit. This drastically
streamlines interacting with ruff.

Enable the git hook with:

```sh
ln -sf ../../.ci/hooks/pre-commit .git/hooks/pre-commit
```

### Shell scripts

* Must be POSIX compliant, so busybox ash can interpret them. (Exception: the
  `local` keyword can also be used, to give variables a local scope inside
  functions).

### Markdown

Markdown files are linted with markdownlint-cli, to avoid having to install npm
on your host, you can lint the markdown files in this repo with:

```sh
pmbootstrap ci markdown
```

Additionally, most electron based IDEs (e.g. vscode) have markdownlint available
as an extension.

## Code patterns

### The `args` variable

This contains the arguments passed to pmbootstrap, and some additional data. See
`pmb/helpers/args.py` for details. This is a legacy construct, see
[#1879](https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/issues/1879).

### Executing commands

Use one of the following functions instead of Python's built-in `subprocess`:

* `pmb.helpers.run.user()`
* `pmb.helpers.run.root()`
* `pmb.chroot.user()`
* `pmb.chroot.root()`

These functions call `pmb.helpers.run_core.core()` internally to write to the
log file (that you can read with `pmbootstrap log`) and timeout when there is no
output. A lot of function parameters are passed through to `core()` as well, see
its docstring for a detailed description of what these parameters do.

#### Using shell syntax

The passed commands do not run inside a shell. If you need to use shell syntax,
wrap your command with `sh -c` and use `shutil.quote` on the parameters (if they
contain untrusted input):

```py
# Does not work, the command does not run in a shell!
pmb.chroot.root(["echo", "test", ">", "/tmp/test"])

# Use this instead (assuming untrusted input for text, dest)
text = "test"
dest = "/tmp/test"
shell_cmd = f"echo {shutil.quote(text)} > {shutil.quote(dest)}"
pmb.chroot.root(["sh", "-c", shell_cmd])
```

If you need to run many commands in a shell at once, write them into a temporary
shell script and execute that with one of the `pmb` command functions.

### Writing files to the chroot

The users in the chroots (`root` and `pmos`) have different user IDs than the
user of the host system. Therefore we can't just write a file to anywhere in the
chroot. Use one of the following methods.

#### Short files

```py
pmb.chroot.user(["sh", "-c", f"echo {shlex.quote(hostname)} > /etc/hostname"], suffix)
```

#### Long files

Write to a temp dir first with python code, then move and chown the file.

```py
with open("tmp/somefile", "w") as handle:
    handle.write("Some long file")
    handle.write("with multiple")
    handle.write("lines here")
pmb.chroot.root(["mv", "/tmp/somefile", "/etc/somefile"])
pmb.chroot.root(["chown", "root:root", "/etc/somefile"], suffix)
```

## Manual testing

### APKBUILD parser

Besides the python tests, it's a good idea to let the APKBUILD parsing code run
over all APKBUILDs that we have in pmaports.git, before and after making
changes. This makes it easy to spot regressions.

```sh
pmbootstrap apkbuild_parse > /tmp/new
git switch main
pmbootstrap apkbuild_parse > /tmp/old
colordiff /tmp/old /tmp/new | less -R
```

## Debugging

### Tab completion

When tab completion breaks, commands-line `pmbootstrap build <TAB>` will simply
not return the expected list of packages anymore. Exceptions are not printed. To
change this behavior and get the exceptions, adjust the `eval
"$(register-python-argcomplete pmbootstrap)"` line in your shell's rc file.

```sh
$ register-python-argcomplete3 pmbootstrap

_python_argcomplete() {
    local IFS=$'\013'
    local SUPPRESS_SPACE=0
    if compopt +o nospace 2> /dev/null; then
        SUPPRESS_SPACE=1
    fi
    COMPREPLY=( $(IFS="$IFS" \
                  COMP_LINE="$COMP_LINE" \
                  COMP_POINT="$COMP_POINT" \
                  COMP_TYPE="$COMP_TYPE" \
                  _ARGCOMPLETE_COMP_WORDBREAKS="$COMP_WORDBREAKS" \
                  _ARGCOMPLETE=1 \
                  _ARGCOMPLETE_SUPPRESS_SPACE=$SUPPRESS_SPACE \
                  "$1" 8>&1 9>&2 1>/dev/null 2>/dev/null) )
    if [[ $? != 0 ]]; then
        unset COMPREPLY
    elif [[ $SUPPRESS_SPACE == 1 ]] && [[ "$COMPREPLY" =~ [=/:]$ ]]; then
        compopt -o nospace
    fi
}
complete -o nospace -o default -F _python_argcomplete "pmbootstrap"
```

Copy the whole output of the command to your shell's rc file instead of the eval
line, but remove `1>/dev/null 2>/dev/null`. Then it will print exceptions to the
shell.
