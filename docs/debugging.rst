#########
Debugging
#########

pmbootstrap writes all log output and each shell command it runs to log.txt inside the work dir.
Use the following command to follow the log in a second terminal: 

.. code-block:: shell

  $ pmbootstrap log


Use ``-v`` on any action to get verbose logging:

.. code-block:: shell

  $ pmbootstrap -v build hello-world


Parse a package from an APKINDEX and return it as JSON:

.. code-block:: shell

  $ pmbootstrap apkindex_parse $WORK/cache_apk_x86_64/APKINDEX.8b865e19.tar.gz hello-world


``ccache`` statistics:

.. code-block:: shell

  $ pmbootstrap stats --arch=armhf


