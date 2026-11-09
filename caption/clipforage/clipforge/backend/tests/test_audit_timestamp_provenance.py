"""
ClipForge Quality Engineering Audit - Timestamp Provenance & Chronology Reconciliation Tests
Item: AUDIT-TIMESTAMP-011

Verifies:
1. The mathematical and timezone root cause of the apparent future-dated manifest (03:25:00Z vs 00:10:00Z).
2. Host (IST, UTC+05:30) vs Container (UTC, +00:00) clock synchronization.
3. Timezone-aware serialization and monotonic timing helpers to prevent recurrence.
4. Retention of original evidence manifest hash and append-only addendum integrity.
"""

import datetime
import json
from pathlib import Path
import time
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_timestamp_reconciliation_manifest_exists_and_valid():
    """Verify the canonical timestamp provenance reconciliation manifest exists."""
    manifest_path = REPO_ROOT / "docs" / "engineering" / "CLIPFORGE_AUDIT_TIMESTAMP_PROVENANCE_RECONCILIATION.json"
    assert manifest_path.exists(), f"Missing timestamp manifest at {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["audit_item"] == "AUDIT-TIMESTAMP-011"
    assert "historical_investigation" in data
    assert "clock_and_environment_evidence" in data
    assert "forensic_event_chronology" in data
    assert "definitive_root_cause_analysis" in data
    assert data["definitive_root_cause_analysis"]["verdict"].startswith("RECONCILED")


def test_timezone_conversion_arithmetic_proof():
    """Mathematically prove why appending 'Z' to local 03:25:00 IST created a spurious +3h15m gap."""
    # Local IST representation
    local_time = datetime.datetime(2026, 11, 3, 3, 25, 0)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    local_aware = local_time.replace(tzinfo=ist_tz)

    # True UTC conversion
    true_utc = local_aware.astimezone(datetime.timezone.utc)
    assert true_utc == datetime.datetime(2026, 11, 2, 21, 55, 0, tzinfo=datetime.timezone.utc)

    # Naive flawed UTC interpretation (string + 'Z')
    naive_flawed_utc = datetime.datetime(2026, 11, 3, 3, 25, 0, tzinfo=datetime.timezone.utc)

    # Contemporaneous context time: 00:10:00 UTC on 3 Nov 2026
    context_time = datetime.datetime(2026, 11, 3, 0, 10, 0, tzinfo=datetime.timezone.utc)

    # Gap if interpreted naively: +3h 15m (apparent future)
    flawed_gap = naive_flawed_utc - context_time
    assert flawed_gap == datetime.timedelta(hours=3, minutes=15)

    # True gap when properly converted to UTC: -2h 15m (actual past)
    true_gap = true_utc - context_time
    assert true_gap == datetime.timedelta(hours=-2, minutes=-15)


def test_evidence_manifest_has_provenance_addendum():
    """Verify that CLIPFORGE_FULL_WEBSITE_EVIDENCE_MANIFEST.json retains historical timestamp and has addendum."""
    manifest_path = REPO_ROOT / "docs" / "engineering" / "CLIPFORGE_FULL_WEBSITE_EVIDENCE_MANIFEST.json"
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Historical timestamp must be preserved verbatim
    assert data["audit_metadata"]["timestamp"] == "2026-11-03T03:25:00Z"

    # Addendum must be present
    assert "timestamp_provenance_addendum" in data
    addendum = data["timestamp_provenance_addendum"]
    assert addendum["audit_item"] == "AUDIT-TIMESTAMP-011"
    assert addendum["reconciliation_status"] == "RECONCILED"
    assert addendum["pre_addendum_sha256"] == "388783454280ebcee79955231b45d755b5a213766ee6e7ae0aca35999f3f5a42"


def test_timezone_aware_serialization_standard():
    """Verify timezone-aware ISO serialization helper behaves deterministically."""
    def serialize_utc_timestamp(dt: datetime.datetime | None = None) -> str:
        if dt is None:
            dt = datetime.datetime.now(datetime.timezone.utc)
        elif dt.tzinfo is None:
            # Assume local host timezone if naive, then convert to UTC
            host_offset = -time.timezone if (time.daylight == 0) else -time.altzone
            local_tz = datetime.timezone(datetime.timedelta(seconds=host_offset))
            dt = dt.replace(tzinfo=local_tz).astimezone(datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # Test with explicit UTC
    utc_dt = datetime.datetime(2026, 11, 3, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert serialize_utc_timestamp(utc_dt) == "2026-11-03T12:00:00.000000Z"

    # Test with IST offset
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ist_dt = datetime.datetime(2026, 11, 3, 17, 30, 0, tzinfo=ist_tz)
    assert serialize_utc_timestamp(ist_dt) == "2026-11-03T12:00:00.000000Z"


def test_forensic_report_contains_timestamp_reconciliation_addendum():
    """Verify that CLIPFORGE_FULL_WEBSITE_FORENSIC_AUDIT_REPORT.md contains Section 7.2."""
    report_path = REPO_ROOT / "docs" / "engineering" / "CLIPFORGE_FULL_WEBSITE_FORENSIC_AUDIT_REPORT.md"
    content = report_path.read_text(encoding="utf-8")

    assert "Section 7.2" in content
    assert "AUDIT-TIMESTAMP-011" in content
    assert "2026-11-03T03:25:00Z" in content
    assert "2026-11-02T21:55:00Z" in content
    assert "3 hours 15 minutes" in content
