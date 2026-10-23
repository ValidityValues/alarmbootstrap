"""Unit tests for the Arch-native alarmbootstrap layer."""

import json

from alarmbootstrap.catalog import BUILTIN_CATALOG, load_catalog, merge_catalogs, parse_deviceinfo
from alarmbootstrap.cli import main
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


def test_catalog_contains_full_nura_id_snapshot() -> None:
    catalog = load_catalog(BUILTIN_CATALOG)
    ids = {item["id"] for item in catalog["devices"]}
    assert len(ids) >= 600
    assert "google-flame" in ids
    assert all(item.get("id") for item in catalog["devices"])


def test_cli_init_and_status(tmp_path, capsys) -> None:
    config = tmp_path / "config" / "config.json"
    workdir = tmp_path / "work"
    assert main([
        "--config", str(config), "init", "--device", "google-flame",
        "--workdir", str(workdir),
    ]) == 0
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["device"] == "google-flame"
    assert data["workdir"] == str(workdir.resolve())
    assert main(["--config", str(config), "status"]) == 0
    output = capsys.readouterr().out
    assert "Arch rootfs: not installed" in output


def test_native_device_query_lists_pixel4(capsys) -> None:
    assert main(["devices", "--query", "google-flame"]) == 0
    output = capsys.readouterr().out
    assert "Google Pixel 4" in output
    assert "Arch-native priority" in output


def test_packaged_catalog_matches_repository_snapshot() -> None:
    from pathlib import Path

    repository_catalog = Path(__file__).resolve().parents[1] / "devices" / "catalog.json"
    packaged = load_catalog(BUILTIN_CATALOG)
    repository = load_catalog(repository_catalog)
    assert {item["id"] for item in packaged["devices"]} == {
        item["id"] for item in repository["devices"]
    }
    assert next(item for item in packaged["devices"] if item["id"] == "google-flame") == next(
        item for item in repository["devices"] if item["id"] == "google-flame"
    )
