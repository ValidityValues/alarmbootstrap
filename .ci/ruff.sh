#!/bin/sh -e
# Description: lint all python scripts
# https://nura.eco/pmb-ci

if [ "$(id -u)" = 0 ]; then
	set -x
	apk -q add py3-pip
	pip install --break-system-packages --no-warn-script-location ruff
	exec su "${TESTUSER:-build}" -c "sh -e $0"
fi

DID_FAIL=0

set -x

# Lint all files
ruff check || DID_FAIL=1

# Check formatting
ruff format --diff || DID_FAIL=1

exit $DID_FAIL
