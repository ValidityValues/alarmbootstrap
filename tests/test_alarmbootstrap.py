"""Unit tests for the Arch-native alarmbootstrap layer."""

from alarmbootstrap.catalog import merge_catalogs, parse_deviceinfo
from alarmbootstrap.pixel4 import DEVICE_ID
from alarmbootstrap.rootfs import DEFAULT_AARCH64_URL


def test_builtin_identity_constants() -> None:
    assert DEVICE_ID == "google-flame"
    assert DEFAULT_AARCH64_URL.endswith("ArchLinuxARM-aarch64-latest.tar.gz")


def test_parse_deviceinfo_does_not_execute_shell() -> None:
    data = parse_deviceinfo(
        'deviceinfo_name="Google Pixel 4"\n'
        "deviceinfo_arch=aarch64\n"
        'deviceinfo_model="$(touch /tmp/not-run)"\n'
    )
    assert data["deviceinfo_name"] == "Google Pixel 4"
    assert data["deviceinfo_arch"] == "aarch64"
    assert data["deviceinfo_model"] == "$(touch /tmp/not-run)"


def test_merge_catalog_preserves_removed_ids() -> None:
    existing = {
        "schema_version": 1,
        "devices": [
            {"id": "google-flame", "name": "Pixel 4", "profile": {"kernel": "sm8150"}},
            {"id": "legacy-phone", "name": "Legacy device"},
        ],
    }
    upstream = {
        "google-flame": {
            "id": "google-flame",
            "name": "Pixel 4 (updated)",
            "upstream_present": True,
        },
        "new-phone": {"id": "new-phone", "name": "New device", "upstream_present": True},
    }
    merged = merge_catalogs(existing, upstream)
    devices = {entry["id"]: entry for entry in merged["devices"]}
    assert set(devices) == {"google-flame", "legacy-phone", "new-phone"}
    assert devices["google-flame"]["name"] == "Pixel 4 (updated)"
    assert devices["google-flame"]["profile"] == {"kernel": "sm8150"}
    assert devices["legacy-phone"]["upstream_present"] is False
    assert devices["new-phone"]["upstream_present"] is True
