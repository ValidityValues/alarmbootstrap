#!/bin/sh -e
# Description: run pmbootstrap python testsuite
# Options: native slow
# https://nura.eco/pmb-ci

if [ "$(id -u)" = 0 ]; then
	set -x
	apk -q add \
		git \
		openssl \
		py3-pytest \
		py3-pytest-cov \
		sudo
	exec su "${TESTUSER:-build}" -c "sh -e $0"
fi

# Require pytest to be installed on the host system
if [ -z "$(command -v pytest)" ]; then
	echo "ERROR: pytest command not found, make sure it is in your PATH."
	exit 1
fi

# Use pytest-cov if it is installed to display code coverage
cov_arg=""
if python -c "import pytest_cov" >/dev/null 2>&1; then
	cov_arg="--cov=pmb --cov-report term --cov-report xml:coverage.xml"
fi

echo "Running pytest..."
echo "NOTE: use 'pmbootstrap log' to see the detailed log if running locally."
# shellcheck disable=SC2086
python -m pytest \
	--color=yes \
	-vv \
	--junitxml=junit.xml \
	$cov_arg \
	-m "not skip_ci" \
	"$@"
