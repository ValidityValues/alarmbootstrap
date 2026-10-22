"""Nura/postmarketOS device catalog import with lossless ID retention."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

NURA_PORTS_URL = "https://gitlab.postmarketos.org/postmarketOS/pmaports.git"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILTIN_CATALOG = REPOSITORY_ROOT / "devices" / "catalog.json"


def _assignment_value(raw: str) -> str:
    """Parse a shell-like literal value without executing the assignment."""
    raw = raw.strip()
    try:
        values = shlex.split(raw, comments=True, posix=True)
        return values[0] if values else ""
    except ValueError:
        return raw.strip("'\"")


def parse_deviceinfo(text: str) -> dict[str, str]:
    """Read literal deviceinfo assignments; never source or execute shell code."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(deviceinfo_[A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
        if match:
            values[match.group(1)] = _assignment_value(match.group(2))
    return values


def scan_pmaports(ports_dir: Path) -> dict[str, dict[str, Any]]:
    """Return all deviceinfo records found below a pmaports checkout."""
    ports_dir = ports_dir.expanduser().resolve()
    device_root = ports_dir / "device"
    if not device_root.is_dir():
        raise ValueError(f"Not a pmaports checkout (missing {device_root})")

    found: dict[str, dict[str, Any]] = {}
    for info_path in sorted(device_root.rglob("deviceinfo")):
        package_dir = info_path.parent
        package_name = package_dir.name
        if not package_name.startswith("device-"):
            continue
        device_id = package_name.removeprefix("device-")
        raw_text = info_path.read_text(encoding="utf-8", errors="replace")
        fields = parse_deviceinfo(raw_text)
        record: dict[str, Any] = {
            "id": device_id,
            "name": fields.get("deviceinfo_name", device_id),
            "manufacturer": fields.get("deviceinfo_manufacturer", ""),
            "arch": fields.get("deviceinfo_arch", "unknown"),
            "source": str(info_path.relative_to(ports_dir)),
            "deviceinfo": fields,
            "deviceinfo_text": raw_text,
            "upstream_present": True,
        }
        if device_id in found:
            found[device_id].setdefault("alternate_sources", []).append(record["source"])
        else:
            found[device_id] = record

    if not found:
        raise ValueError(f"No deviceinfo files found below {device_root}")
    return found


def load_catalog(path: Path = BUILTIN_CATALOG) -> dict[str, Any]:
    """Load a catalog and reject invalid or duplicate IDs."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("devices"), list):
        raise ValueError(f"Invalid device catalog: {path}")
    seen: set[str] = set()
    for item in value["devices"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError(f"Catalog entry without string id in {path}")
        if item["id"] in seen:
            raise ValueError(f"Duplicate device id {item['id']} in {path}")
        seen.add(item["id"])
    return value


def merge_catalogs(
    existing: dict[str, Any], upstream: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Refresh metadata without silently deleting device IDs or local profiles."""
    old_devices = {item["id"]: dict(item) for item in existing.get("devices", [])}
    merged: dict[str, dict[str, Any]] = {}

    for device_id, current in upstream.items():
        if device_id in old_devices:
            old = old_devices.pop(device_id)
            profile = old.get("profile")
            result = {**old, **current, "upstream_present": True}
            if profile is not None:
                result["profile"] = profile
            merged[device_id] = result
        else:
            merged[device_id] = dict(current)

    for device_id, old in old_devices.items():
        old["upstream_present"] = False
        old["catalog_status"] = "retired-upstream-entry-preserved"
        merged[device_id] = old

    return {
        "schema_version": 1,
        "source": NURA_PORTS_URL,
        "devices": sorted(merged.values(), key=lambda item: item["id"]),
    }


def sync_nura_catalog(
    output: Path,
    ports_dir: Path | None = None,
    existing_catalog: Path = BUILTIN_CATALOG,
) -> dict[str, Any]:
    """Sync from a checkout or temporary shallow clone, preserving previous entries."""
    output = output.expanduser().resolve()
    previous_path = output if output.is_file() else existing_catalog
    existing = load_catalog(previous_path) if previous_path.exists() else {
        "schema_version": 1,
        "devices": [],
    }

    def write_from(ports: Path) -> dict[str, Any]:
        upstream = scan_pmaports(ports)
        result = merge_catalogs(existing, upstream)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return result

    if ports_dir is not None:
        return write_from(ports_dir)

    with tempfile.TemporaryDirectory(prefix="alarmbootstrap-pmaports-") as temp:
        checkout = Path(temp) / "pmaports"
        subprocess.run(
            ["git", "clone", "--depth=1", NURA_PORTS_URL, str(checkout)],
            check=True,
        )
        return write_from(checkout)
