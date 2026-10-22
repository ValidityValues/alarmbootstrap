
#####
Usage
#####

pmbootstrap offers many options and actions and is normally ran from a shell.


Before pmbootstrap can be used, a number of configuration questions need to be answered. The sections below go into detail for the various questions.

.. code-block:: shell

  $ pmbootstrap init

If you already ran this before, run the following to update your local clone of pmaports.git instead, before moving straight onto the installation step:

.. code-block:: shell

   $ pmbootstrap pull


Quick health check and config overview:

.. code-block:: shell

   $ pmbootstrap status


After successfully finishing the ``init`` sequence with answering all questions, its time to build the
installation:

Devices like the PinePhone, Samsung Galaxy S II, Nokia N900, various laptops etc. can boot from an SD card, USB stick or other external storage. Find the name with lsblk first and make sure it is the right one as you will overwrite everything on it. Use a path without partition number at the end, such as /dev/mmcblk0. If your device is able to boot from SD card without flashing anything (such as the PinePhone), you should then be able to insert SD card into your device and boot it up.

.. code-block:: shell

   $ pmbootstrap install --sdcard=/dev/mmcblk... --fde


For devices where you will flash directly to the internal storage, as mostly all sdm845 devices, you can build the installation as:

.. code-block:: shell

   $ pmbootstrap install


or with full disk encryption:

.. code-block:: shell

   $ pmbootstrap install --fde

and then flash it with the ``pmbootstrap flasher`` while the device is in ``fastboot`` mode:

.. code-block:: shell

   $ pmbootstrap flasher flash_rootfs


and also the kernel:

.. code-block:: shell

   $ pmbootstrap flasher flash_kernel


For getting images on the local machine instead of directly flashing them, execute:

.. code-block:: shell

   $ pmbootstrap export


To extract the generated initramfs:

.. code-block:: shell

   $ pmbootstrap initfs extract


Build and flash Android recovery zip:

.. code-block:: shell

 $ pmbootstrap install --android-recovery-zip
 $ pmbootstrap flasher --method=adb sideload


Update existing installation on SD card:

.. code-block:: shell

 $ pmbootstrap install --disk=/dev/mmcblk0 --rsync


Run the image in QEMU:

.. code-block:: shell

 $ pmbootstrap qemu --image-size=1G


**Device Porting Assistance**

Analyze Android boot.img files (also works with recovery OS images like TWRP):

.. code-block:: shell

 $ pmbootstrap bootimg_analyze ~/Downloads/twrp-3.2.1-0-fp2.img


Check kernel configs:

.. code-block:: shell

 $ pmbootstrap kconfig check


Edit a kernel config:

.. code-block:: shell

 $ pmbootstrap kconfig edit



For further details on the different actions please see below and refer to the wiki-arcticle on `pmbootstrap`_.

.. autoprogram:: pmb.parse:get_parser()
   :prog: pmbootstrap
   :groups:

Requirements
============

pmbootstrap requires the following:

  * Linux distribution on the host system (`x86`, `x86_64`, `aarch64` or `armv7`)

    .. note::
       Windows subsystem for `Linux (WSL)`_ does **not** work! Please use `VirtualBox`_ instead.


  * Linux kernel 3.17 or higher (`oldkernel`_)

    .. note::
       Kernel version 5.8 - 6.0 might have issues with loop-devices


  * Python 3.10+
  * For python3 < 3.11: tomli
  * OpenSSL
  * git
  * ps
  * tar
  * sudo, doas, or run0
  * POSIX-shell (`ash`,`bash`, `zfs` reported to work)

.. _pmbootstrap: https://wiki.postmarketos.org/wiki/Pmbootstrap#Using_pmbootstrap

.. _Linux (WSL): https://en.wikipedia.org/wiki/Windows_Subsystem_for_Linux

.. _virtualbox: https://www.virtualbox.org/

.. _oldkernel: https://postmarketos.org/oldkernel

