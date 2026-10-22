######
Chroot
######

chroot (short for "change root") is a system call and command that changes the apparent root directory.
This can come in very handy to make some modifications in the generated image file.



Enter the armhf building chroot:

.. code-block:: shell

  $ pmbootstrap chroot -b armhf


Run a command inside a chroot:

.. code-block:: shell

  $ pmbootstrap chroot -- echo test


Safely delete all chroots:

.. code-block:: shell

  $ pmbootstrap zap



Use ``chroot`` to install a specific kernel version from an apk file. 


copy your working kernel apk to the chroot dir of pmbootstrap:

.. code-block:: shell

  $ sudo cp /path/of/linux-kernel.apk ~/.local/var/pmbootstrap/chroot_rootfs_oneplus-enchilada/ 

enter chroot

.. code-block:: shell

  $ pmbootstrap chroot -r 


and install the package:

.. code-block:: shell

 $ apk add linux-kernel.apk


