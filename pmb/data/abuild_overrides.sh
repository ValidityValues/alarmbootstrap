# shellcheck shell=sh
# BEGIN PMBOOTSTRAP OVERRIDES

# shellcheck disable=SC3043,SC2086,SC2154,SC2155,SC2034,SC3003,SC3057
sumcheck() {
	local sums="$1"
	local dummy f endreturnval originalparams origin file

	# get number of checksums
	set -- $sums
	local numsums=$(($# / 2))

	set -- $source
	if [ $# -ne $numsums ]; then
		die "Number of sha512sums($numsums) does not correspond to number of sources($#)"
	fi
	fetch || return 1
	msg "Checking sha512sums..."
	cd "$srcdir" || return 1
	IFS=$'\n'
	endreturnval=0
	for src in $sums; do
		origin=$1
		shift
		if ! echo "$src" | sha512sum -c; then
			if is_remote $origin; then
				endreturnval=2
			else
				if [ "$endreturnval" -ne 2 ]; then
					endreturnval=1
				fi
				continue
			fi

			local csum="${src:0:8}"
			local file="$SRCDEST/$(filename_from_uri $origin)"
			mv "$file" "$file.$csum"
		fi
	done
	unset IFS
	return $endreturnval
}

# Patched version of verify() to only warn instead of
# refusing to build.
# shellcheck disable=SC2034,SC2154,SC3043
verify() {
	rm -f /tmp/apkbuild_verify_failed
	local verified=false algo=
	sumcheck "$sha512sums" && verified=true
	retval=$?
	if [ $retval -eq 2 ]; then
		echo "network" >/tmp/apkbuild_verify_failed
		die "Failed to verify checksums of remote sources. The file has been renamed" >&2
	fi
	if [ -n "$source" ] && ! $verified; then
		echo "local" >/tmp/apkbuild_verify_failed
	fi
	return 0
}

# END PMBOOTSTRAP OVERRIDES
