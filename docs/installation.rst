
Installation
============

pmbootstrap runs on pretty much any Linux distribution with a POSIX-shell [1]_ and python3, openssl, git installed. It uses Alpine Linux chroots internally to avoid installing software on the host machine. If you don't run Linux on your PC, see :ref:`other-os`. 

On Linux
--------

From package manager
^^^^^^^^^^^^^^^^^^^^

.. code-block::

   Alpine Linux, postmarketOS:
   # apk add pmbootstrap
   Arch Linux:
   # pacman -S pmbootstrap
   Debian:
   # apt install pmbootstrap
   Fedora:
   # dnf install pmbootstrap
   Void Linux:
   # xbps-install -S pmbootstrap
   Gentoo:
   # emerge -va app-eselect/eselect-repository
   # eselect repository enable guru
   # emaint -r guru sync
   # emerge -va dev-util/pmbootstrap
   Nix/NixOS
   # nix run nixpkgs#pmbootstrap

.. note::
   Fixed release distributions, i.e. Debian, may freeze pmbootstrap version. Consider installing it from git if you want the latest features and bug fixes.

From git
^^^^^^^^
Follow this section if your Linux distribution doesn't have pmbootstrap packaged, or its version of pmbootstrap is too old, or you would like to change the code. Run the following to clone and install pmbootstrap from git. 


.. code-block::
   
   $ git clone --depth=1 https://gitlab.postmarketos.org/postmarketOS/pmbootstrap.git
   $ mkdir -p ~/.local/bin
   $ ln -s "$PWD/pmbootstrap/pmbootstrap.py" ~/.local/bin/pmbootstrap
   $ pmbootstrap --version
   2.1.0

If this returns something like `pmbootstrap: command not found instead` of a version number, ensure that `~/.local/bin` is in your `PATH`. For example by adding the following to your `~/.profile` (zsh: `~/.zprofile`) followed by `source ~/.profile` to update your environment. 

.. code-block::

   PATH="$HOME/.local/bin:$PATH"

Then open a new terminal and try again. 

.. _other-os:

On other operating systems
--------------------------

Running pmbootstrap on other operating systems than Linux is not supported. If you run another OS, consider setting up a virtual machine with Linux. 

Some people also made it work with WSL, see the `Windows FAQ`_ in the pmOS-Wiki. 
But again, it's not officially supported - we recommend getting some sort of Linux install instead and running it there.

.. _Windows FAQ: https://wiki.postmarketos.org/wiki/Windows_FAQ

.. [1] `ash`, `bash` and `zsh` are reported fine with pmbootstrap, `Nushell` has been reported to cause issues with the fde-integration
