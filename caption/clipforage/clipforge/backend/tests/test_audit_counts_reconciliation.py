"""
ClipForge Quality Engineering Audit - Control-Count Arithmetic Reconciliation Tests
Item: AUDIT-COUNTS-009

Verifies the mathematical and forensic reconciliation of the full website audit
control counts (411/122/296 vs 407/141/306) across raw DOM, visible controls,
and component-level unique inventories.
"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_reconciliation_manifest_exists_and_valid():
    """Verify the canonical reconciliation manifest exists and contains required sections."""
    manifest_path = REPO_ROOT / "docs" / "engineering" / "CLIPFORGE_AUDIT_CONTROL_COUNTS_RECONCILIATION.json"
    assert manifest_path.exists(), f"Missing reconciliation manifest at {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["audit_item"] == "AUDIT-COUNTS-009"
    assert "historical_findings" in data
    assert "methodology_and_selectors" in data
    assert "live_remeasurement_audit" in data
    assert data["reconciliation_verdict"]["status"] == "RECONCILED"


def test_historical_manifest_mechanical_sums():
    """Verify that responsive_walkthrough_manifest.json sums mechanically to 407, 141, 306."""
    walkthrough_path = REPO_ROOT / "tmp" / "clipforge_full_website_audit" / "responsive_walkthrough_manifest.json"
    assert walkthrough_path.exists(), f"Historical walkthrough manifest missing at {walkthrough_path}"

    with open(walkthrough_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data["results"]
    assert len(results) == 9, f"Expected 9 pages in historical audit, found {len(results)}"

    expected_page_counts = {
        "/": (54, 3, 10),
        "/podcasts": (3, 0, 10),
        "/studio": (3, 2, 10),
        "/clips": (210, 101, 160),
        "/analytics": (15, 1, 10),
        "/automation": (91, 21, 42),
        "/youtube-channels": (19, 0, 14),
        "/publish": (6, 3, 40),
        "/settings": (6, 10, 10),
    }

    buttons_total = 0
    inputs_total = 0
    links_total = 0

    for r in results:
        path = r["path"]
        assert path in expected_page_counts, f"Unexpected route in walkthrough: {path}"
        expected_b, expected_i, expected_l = expected_page_counts[path]

        for vp_name, vp_data in r["viewports"].items():
            inter = vp_data["interactive"]
            assert inter["buttons"] == expected_b, f"Mismatch on {path} {vp_name} buttons"
            assert inter["inputs"] == expected_i, f"Mismatch on {path} {vp_name} inputs"
            assert inter["links"] == expected_l, f"Mismatch on {path} {vp_name} links"

        # Accumulate desktop counts
        desktop = r["viewports"]["desktop"]["interactive"]
        buttons_total += desktop["buttons"]
        inputs_total += desktop["inputs"]
        links_total += desktop["links"]

    # Mechanical derivation assertions:
    assert buttons_total == 407, f"Buttons sum should be 407, got {buttons_total}"
    assert inputs_total == 141, f"Inputs sum should be 141, got {inputs_total}"
    assert links_total == 306, f"Links sum should be 306, got {links_total}"
    assert buttons_total + inputs_total + links_total == 854


def test_discrepancy_arithmetic_precision():
    """Verify the exact arithmetic delta between historical claim and mechanical derivation."""
    claimed_buttons = 411
    claimed_inputs = 122
    claimed_links = 296

    derived_buttons = 407
    derived_inputs = 141
    derived_links = 306

    delta_buttons = claimed_buttons - derived_buttons
    delta_inputs = claimed_inputs - derived_inputs
    delta_links = claimed_links - derived_links

    # Proof of exact discrepancy values
    assert delta_buttons == 4, "Buttons discrepancy must be exactly +4 (overclaim)"
    assert delta_inputs == -19, "Inputs discrepancy must be exactly -19 (underclaim)"
    assert delta_links == -10, "Links discrepancy must be exactly -10 (underclaim)"


def test_live_remeasurement_multi_tier_integrity():
    """Verify the live measurement audit file adheres to multi-tier classification schema."""
    live_path = REPO_ROOT / "tmp" / "clipforge_full_website_audit" / "reconciled_audit_counts_live.json"
    assert live_path.exists(), f"Live remeasurement manifest missing at {live_path}"

    with open(live_path, "r", encoding="utf-8") as f:
        live_data = json.load(f)

    assert live_data.get("auditItem") == "AUDIT-COUNTS-009" or live_data.get("audit_item") == "AUDIT-COUNTS-009"
    measurements = live_data["routeMeasurements"]
    assert len(measurements) == 9, f"Expected 9 measured routes, got {len(measurements)}"

    # Check each route has both raw counts and interactive breakdown
    for m in measurements:
        assert "historicalAuditCounts" in m
        assert "interactiveBreakdown" in m
        ib = m["interactiveBreakdown"]
        for cat in ("buttons", "inputs", "links"):
            assert cat in ib
            assert ib[cat]["totalDom"] >= ib[cat]["visibleEnabled"]
            assert ib[cat]["totalDom"] == ib[cat]["shell"] + ib[cat]["body"]

    # Verify shell navigation persistence (sidebar has 9 links on every page)
    for m in measurements:
        assert m["interactiveBreakdown"]["links"]["shell"] == 9, (
            f"Expected 9 shell navigation links on {m['path']}, got {m['interactiveBreakdown']['links']['shell']}"
        )


def test_forensic_report_contains_reconciliation_addendum():
    """Verify that CLIPFORGE_FULL_WEBSITE_FORENSIC_AUDIT_REPORT.md documents the arithmetic reconciliation."""
    report_path = REPO_ROOT / "docs" / "engineering" / "CLIPFORGE_FULL_WEBSITE_FORENSIC_AUDIT_REPORT.md"
    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")
    assert "Arithmetic Reconciliation Addendum" in content
    assert "407" in content
    assert "141" in content
    assert "306" in content
    assert "AUDIT-COUNTS-009" in content
