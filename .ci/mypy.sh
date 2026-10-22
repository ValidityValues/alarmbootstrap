#!/bin/sh -e
# Description: static type checking for python scripts
# https://nura.eco/pmb-ci

if [ "$(id -u)" = 0 ]; then
	set -x
	apk -q add py3-argcomplete py3-pip py3-pytest
	exec su "${TESTUSER:-build}" -c "sh -e $0"
fi

set -x

pip install --break-system-packages --no-warn-script-location mypy
python -m mypy .
