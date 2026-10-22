
################
SSH Key Handling
################

pmbootstrap can copy SSH keys to the device during the install step.

If the config file option `ssh_keys` is set to `True` (it defaults to `False`),
then all files matching the glob `~/.ssh/*.pub` will be placed in
`~/.ssh/authorized_keys` in the user's home directory in newly-built images.

Sometimes, for example if you have a large number of SSH keys, you may wish to
select a different set of public keys to include in an image. To do this, set
the `ssh_key_glob` configuration parameter in the pmbootstrap config file to a
string containing a glob that is to match the file or files you wish to
include.

For example, a `~/.config/pmbootstrap_v3.cfg` may contain:

.. code-block:: shell

    [pmbootstrap]
    # ...
    ssh_keys = True
    ssh_key_glob = ~/.ssh/postmarketos-dev.pub
    # ...

