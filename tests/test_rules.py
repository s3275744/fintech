from decimal import Decimal

from fiskal.data_loader import load_profile, parse_money
from fiskal.payloads import build_ledger_payload
from fiskal.rules import build_dashboard, find_summary


def test_transaction_level_review_items_are_attached_to_rows():
    dashboard = build_dashboard(load_profile("small"))
    review = find_summary(dashboard, "S-003")
    transactions_needing_review = [tx for tx in review["transactions"] if tx["needs_correction"]]

    assert review["status"] == "Review"
    assert review["open_transaction_issue_count"] == 1
    assert {tx["transaction_id"] for tx in transactions_needing_review} == {"S-T008"}
    receipt_row = transactions_needing_review[0]
    assert receipt_row["receipt"] == {
        "required": True,
        "status": "missing",
        "value": "Missing",
        "label": "Receipt ID",
    }


def test_profiles_load_with_expected_sizes():
    small = load_profile("small")
    medium = load_profile("medium")
    large = load_profile("large")

    assert len(small["clients"]) == 8
    assert len(medium["clients"]) == 16
    assert len(large["clients"]) == 24


def test_money_parser_handles_messy_amounts():
    assert parse_money("2,450.00") == Decimal("2450.00")
    assert parse_money(" 2,600.00 ") == Decimal("2600.00")
    assert parse_money("96,50") == Decimal("96.50")


def test_ready_review_and_flagged_statuses_exist():
    dashboard = build_dashboard(load_profile("medium"))
    statuses = {client["status"] for client in dashboard["clients"]}

    assert "Ready" in statuses
    assert "Review" in statuses
    assert "Flagged" in statuses
    assert "Filed" in statuses


def test_dashboard_summary_counts_include_filed_clients():
    dashboard = build_dashboard(load_profile("small"))

    assert dashboard["total_clients"] == 8
    assert dashboard["ready_count"] == 4
    assert dashboard["review_count"] == 2
    assert dashboard["flagged_count"] == 1
    assert dashboard["filed_count"] == 1


def test_approved_clients_count_as_filed():
    data = load_profile("small")
    ready = find_summary(build_dashboard(data), "S-001")
    payload = build_ledger_payload(data["office"], ready)
    dashboard = build_dashboard(data, approvals={"S-001": payload})
    filed = find_summary(dashboard, "S-001")

    assert filed["status"] == "Filed"
    assert filed["status_key"] == "filed"
    assert filed["queue_note"] == "Filed after bookkeeper approval"
    assert filed["is_approved"] is True
    assert filed["can_approve"] is False
    assert dashboard["ready_count"] == 3
    assert dashboard["filed_count"] == 2


def test_dashboard_renders_filed_kpi_tile():
    from app import app

    client = app.test_client()
    response = client.get("/?profile=small")

    assert response.status_code == 200
    assert b"kpi-filed" in response.data
    assert b"<span>Filed</span>" in response.data
    assert b"Already submitted" in response.data


def test_flagged_client_has_lower_confidence_than_ready_client():
    dashboard = build_dashboard(load_profile("small"))
    ready = find_summary(dashboard, "S-001")
    flagged = find_summary(dashboard, "S-005")

    assert ready["status"] == "Ready"
    assert flagged["status"] == "Flagged"
    assert flagged["confidence"] < ready["confidence"]


def test_review_client_cannot_be_approved_in_bulk():
    dashboard = build_dashboard(load_profile("small"))
    review = find_summary(dashboard, "S-003")

    assert review["status"] == "Review"
    assert review["can_approve"] is False


def test_review_items_are_source_pdf_extraction_uncertainty():
    dashboard = build_dashboard(load_profile("small"))
    review = find_summary(dashboard, "S-003")
    review_messages = [item["message"] for tx in review["transactions"] for item in tx["review_items"]]

    assert any("source PDF" in message for message in review_messages)
    assert any("handwritten value" in message for message in review_messages)
    assert all("KOR" not in message for message in review_messages)
    assert all(item["severity"] == "review" for tx in review["transactions"] for item in tx["review_items"])


def test_review_contact_is_fallback_not_auto_resolution():
    data = load_profile("small")
    dashboard = build_dashboard(
        data,
        review_contacts={
            "S-T008": {
                "subject": "Please confirm value for S-T008",
                "request": "Can you confirm the receipt id?",
                "reply": "The value is TS 520-78416.",
                "confirmed_value": "TS 520-78416",
            }
        },
    )
    review = find_summary(dashboard, "S-003")
    receipt_row = next(tx for tx in review["transactions"] if tx["transaction_id"] == "S-T008")
    receipt_item = receipt_row["review_items"][0]

    assert review["status"] == "Review"
    assert receipt_item["review_contact"]["confirmed_value"] == "TS 520-78416"
    assert receipt_item["resolved"] is False


def test_flagged_evidence_flow_clears_compliance_flag():
    data = load_profile("large")
    flagged = find_summary(build_dashboard(data), "L-003")

    assert flagged["status"] == "Flagged"
    flagged_row = next(tx for tx in flagged["transactions"] if tx["transaction_id"] == "L-T007")
    assert flagged_row["review_status"] == "flagged"
    assert flagged_row["evidence"]["vat_value"] == "Missing"
    assert flagged_row["evidence"]["transport_value"] == "Missing"

    requested = build_dashboard(
        data,
        evidence_records={
            "L-T007": {
                "subject": "Missing evidence for L-T007",
                "request": "Please send VAT number evidence and transport proof.",
                "reply": "Attached is the evidence PDF.",
                "analysis": "Evidence found.",
                "accepted": False,
            }
        },
    )
    still_flagged = find_summary(requested, "L-003")
    requested_row = next(tx for tx in still_flagged["transactions"] if tx["transaction_id"] == "L-T007")
    assert still_flagged["status"] == "Flagged"
    assert requested_row["evidence"]["vat_value"] == "PDF received, not analysed"

    accepted = build_dashboard(
        data,
        evidence_records={
            "L-T007": {
                "subject": "Missing evidence for L-T007",
                "request": "Please send VAT number evidence and transport proof.",
                "reply": "Attached is the evidence PDF.",
                "analysis": "Evidence found.",
                "accepted": True,
            }
        },
    )
    after_evidence = find_summary(accepted, "L-003")
    evidence_row = next(tx for tx in after_evidence["transactions"] if tx["transaction_id"] == "L-T007")

    assert evidence_row["review_status"] == "corrected"
    assert evidence_row["evidence"]["vat_value"] == "BE 0731.445.221"
    assert evidence_row["evidence"]["transport_value"] == "CMR-2026-Q2-118"
    assert after_evidence["status"] == "Review"

    ready = find_summary(
        build_dashboard(
            data,
            corrections={"L-T008": "KT 514-6B31"},
            evidence_records={
                "L-T007": {
                    "subject": "Missing evidence for L-T007",
                    "request": "Please send VAT number evidence and transport proof.",
                    "reply": "Attached is the evidence PDF.",
                    "analysis": "Evidence found.",
                    "accepted": True,
                }
            },
        ),
        "L-003",
    )
    assert ready["status"] == "Ready"


def test_flagged_service_does_not_require_transport_proof():
    data = load_profile("small")
    flagged = find_summary(build_dashboard(data), "S-005")

    assert flagged["status"] == "Flagged"
    flagged_row = next(tx for tx in flagged["transactions"] if tx["transaction_id"] == "S-T013")
    assert flagged_row["vat_code"] == "EU_REVERSE"
    assert flagged_row["vat_comment"] == "VAT to be accounted for by the recipient"
    assert flagged_row["evidence"]["vat_value"] == "Missing"
    assert flagged_row["evidence"]["transport_value"] == "Not required"
    assert flagged_row["evidence"]["transport_label"] == "No goods shipment"

    ready = find_summary(
        build_dashboard(
            data,
            evidence_records={
                "S-T013": {
                    "subject": "Missing evidence for S-T013",
                    "request": "Please send VAT number evidence.",
                    "reply": "Attached is the evidence PDF.",
                    "analysis": "Evidence found.",
                    "accepted": True,
                }
            },
        ),
        "S-005",
    )
    assert ready["status"] == "Ready"
    assert ready["queue_note"] == "Ready after resolved review items"


def test_correcting_all_transaction_issues_makes_client_ready():
    data = load_profile("small")
    corrections = {
        "S-T008": "TS 520-78416",
    }
    dashboard = build_dashboard(data, corrections=corrections)
    review = find_summary(dashboard, "S-003")
    receipt_row = next(tx for tx in review["transactions"] if tx["transaction_id"] == "S-T008")

    assert review["status"] == "Ready"
    assert review["can_approve"] is True
    assert review["open_transaction_issue_count"] == 0
    assert review["corrected_transaction_count"] == 1
    assert review["queue_note"] == "Ready after resolved review items"
    assert receipt_row["receipt"]["status"] == "entered"
    assert receipt_row["receipt"]["value"] == "TS 520-78416"


def test_payload_contains_no_real_api_notice():
    data = load_profile("small")
    summary = find_summary(build_dashboard(data), "S-001")
    payload = build_ledger_payload(data["office"], summary)

    assert payload["sandbox_notice"] == "No external API call is made."
    assert payload["target_ledger"] == "Moneybird"
    assert payload["quarter"] == "Q2 2026"
    assert payload["vat_totals"]["vat_due_eur"] > 0
    assert payload["approval_checks"]["all_transaction_issues_resolved"] is True
    assert payload["source_transactions"]


def test_payload_includes_source_rows_and_review_audit():
    data = load_profile("small")
    summary = find_summary(
        build_dashboard(data, corrections={"S-T008": "TS 520-78416"}),
        "S-003",
    )
    payload = build_ledger_payload(data["office"], summary)
    source_rows = {row["transaction_id"]: row for row in payload["source_transactions"]}

    assert payload["classification"]["status_before_approval"] == "Ready"
    assert payload["approval_checks"] == {
        "all_transaction_issues_resolved": True,
        "open_transaction_issue_count": 0,
        "corrected_transaction_count": 1,
    }
    assert set(source_rows) == {"S-T007", "S-T008", "S-T009"}
    assert source_rows["S-T008"]["receipt_id"] == "TS 520-78416"
    assert source_rows["S-T008"]["review_status"] == "corrected"
    assert source_rows["S-T008"]["source_document_ref"] == "S-T008.pdf"
    assert source_rows["S-T008"]["evidence"] == {"required": False}
    assert payload["review_audit"] == [
        {
            "transaction_id": "S-T008",
            "issue_type": "Unclear source PDF",
            "resolution": "manual_receipt_entry",
            "entered_value": "TS 520-78416",
        }
    ]


def test_sample_pdf_route_returns_pdf():
    from app import app

    client = app.test_client()
    response = client.get("/sample-document/small/S-T008.pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")


def test_sample_pdf_keeps_fiskal_notes_as_annotations():
    from app import app

    client = app.test_client()
    response = client.get("/sample-document/large/L-T007.pdf")
    content_stream = response.data.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]

    assert b"/Subtype /Text" in response.data
    assert b"Ledger export VAT code: EU_REVERSE" in response.data
    assert b"Synthetic source PDF generated" not in response.data
    assert b"VAT code in ledger export" not in content_stream
    assert b"Reverse charge invoice" not in content_stream
    assert b"This synthetic invoice is generated" not in content_stream
    assert b"legal basis for zero VAT" not in response.data
    assert b"Amount payable" in content_stream
    assert b"Payment reference" in content_stream
    assert b"Exported from" in content_stream


def test_review_receipt_pdf_has_ocr_hard_value_in_body():
    from app import app

    client = app.test_client()
    response = client.get("/sample-document/small/S-T008.pdf")
    content_stream = response.data.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]

    assert b"Receipt id:" in content_stream
    assert b"274 613 130 25" in content_stream
    assert b"190 626 Td (Receipt id:)" in content_stream
    assert b"PURCHASE RECEIPT" in content_stream
    assert b"Terminal 03" in content_stream
    assert b"Thank you, keep this receipt" in content_stream
    assert b"[unreadable]" not in content_stream
    assert b"RC-S003-TR" not in content_stream
    for character in b"TS52078416":
        assert f"({chr(character)})".encode() in content_stream
    assert b"low OCR confidence" in response.data


def test_evidence_pdf_route_returns_pdf():
    from app import app

    client = app.test_client()
    response = client.get("/evidence-document/large/L-T007.pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    content_stream = response.data.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]
    assert b"Evidence PDF" in content_stream
    assert b"Email summary" in content_stream
    assert b"Verification code" in content_stream
    assert b"VAT number and transport reference are readable." in content_stream


def test_service_evidence_pdf_does_not_include_transport_proof():
    from app import app

    client = app.test_client()
    response = client.get("/evidence-document/small/S-T013.pdf")
    content_stream = response.data.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]

    assert response.status_code == 200
    assert b"VAT evidence" in content_stream
    assert b"Buyer VAT number" in content_stream
    assert b"Transport proof" not in content_stream