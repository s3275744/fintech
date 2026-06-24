from collections import Counter, defaultdict
from decimal import Decimal

KNOWN_VAT_CODES = {"NL_HIGH", "NL_LOW", "NL_ZERO", "NL_EXEMPT", "EU_REVERSE"}

VAT_CODE_COMMENTS = {
    "EU_REVERSE": "VAT to be accounted for by the recipient",
}

DEFAULT_EVIDENCE_VALUES = {
    "buyer_vat_number": "BE 0731.445.221",
    "transport_proof": "CMR-2026-Q2-118",
}


PENALTIES = {
    "missing_receipt": 8,
    "reverse_charge": 22,
    "unknown_vat_code": 28,
    "manual_exception": 12,
}


def money(value):
    return float(value.quantize(Decimal("0.01")))


def status_key(status):
    return status.lower().replace(" ", "-")


def needs_transport_proof(*parts):
    text = " ".join(str(part).lower() for part in parts if part)
    return any(keyword in text for keyword in ("goods", "shipment", "transport proof"))


def confidence_for(client_id, warnings):
    base = 96
    stable_noise = (sum(ord(char) for char in client_id) % 5) - 2
    penalty = sum(item["penalty"] for item in warnings)
    score = base + stable_noise - penalty
    return max(35, min(98, score))


def warning(issue_type, severity, message, penalty_key="manual_exception", transaction_id=None):
    return {
        "issue_type": issue_type,
        "severity": severity,
        "message": message,
        "penalty": PENALTIES.get(penalty_key, PENALTIES["manual_exception"]),
        "transaction_id": transaction_id,
    }


def related_transactions_for_exception(issue_type, client_transactions):
    issue = issue_type.lower()

    if "reverse" in issue or "foreign" in issue or "intra" in issue or "uk" in issue:
        matches = [tx for tx in client_transactions if tx["vat_code"] == "EU_REVERSE"]
    elif "receipt" in issue:
        matches = [tx for tx in client_transactions if not tx["receipt_id"]]
    else:
        matches = []

    return matches[:3]


def transaction_status(review_items):
    open_items = [item for item in review_items if not item["resolved"]]
    if any(item["severity"] == "flag" for item in open_items):
        return "flagged"
    if open_items:
        return "review"
    if review_items:
        return "corrected"
    return "clear"


def transaction_receipt_field(transaction, review_items):
    if transaction.get("receipt_id"):
        return {
            "required": False,
            "status": "present",
            "value": transaction["receipt_id"],
            "label": "Receipt ID",
        }

    receipt_review = next((item for item in review_items if item["severity"] == "review"), None)
    if not receipt_review:
        return {
            "required": False,
            "status": "not-required",
            "value": "-",
            "label": "-",
        }

    if receipt_review["resolved"]:
        return {
            "required": True,
            "status": "entered",
            "value": receipt_review.get("correction_note") or "Entered",
            "label": "Receipt ID entered",
        }

    return {
        "required": True,
        "status": "missing",
        "value": "Missing",
        "label": "Receipt ID",
    }


def transaction_evidence_fields(review_items):
    evidence_items = [item for item in review_items if item.get("requires_evidence")]
    if not evidence_items:
        return {
            "required": False,
            "status": "not-required",
            "vat_label": "-",
            "vat_value": "-",
            "transport_required": False,
            "transport_label": "-",
            "transport_value": "-",
        }

    issue_text = " ".join(f"{item['issue_type']} {item['message']}".lower() for item in evidence_items)
    needs_transport = needs_transport_proof(issue_text)
    evidence_record = next((item.get("evidence_record") for item in evidence_items if item.get("evidence_record")), None)
    accepted = bool(evidence_record and evidence_record.get("accepted"))
    received = bool(evidence_record)
    transport_label = "Transport proof" if needs_transport else "No goods shipment"

    if accepted:
        return {
            "required": True,
            "status": "accepted",
            "vat_label": "Buyer VAT number evidence",
            "vat_value": evidence_record.get("buyer_vat_number") or DEFAULT_EVIDENCE_VALUES["buyer_vat_number"],
            "transport_required": needs_transport,
            "transport_label": transport_label,
            "transport_value": (evidence_record.get("transport_proof") or DEFAULT_EVIDENCE_VALUES["transport_proof"]) if needs_transport else "Not required",
        }

    if received:
        return {
            "required": True,
            "status": "received",
            "vat_label": "Buyer VAT number evidence",
            "vat_value": "PDF received, not analysed",
            "transport_required": needs_transport,
            "transport_label": transport_label,
            "transport_value": "PDF received, not analysed" if needs_transport else "Not required",
        }

    return {
        "required": True,
        "status": "missing",
        "vat_label": "Buyer VAT number evidence",
        "vat_value": "Missing",
        "transport_required": needs_transport,
        "transport_label": transport_label,
        "transport_value": "Missing" if needs_transport else "Not required",
    }


def analyze_client(
    client,
    transactions,
    exceptions,
    approved_payload=None,
    corrected_transactions=None,
    evidence_records=None,
    review_contacts=None,
):
    corrected_transactions = corrected_transactions or {}
    evidence_records = evidence_records or {}
    review_contacts = review_contacts or {}
    client_transactions = [tx for tx in transactions if tx["client_id"] == client["client_id"]]
    client_exceptions = [item for item in exceptions if item["client_id"] == client["client_id"]]

    warnings = []
    transaction_reviews = defaultdict(list)
    revenue = Decimal("0")
    input_vat = Decimal("0")
    output_vat = Decimal("0")

    def add_warning(issue_type, severity, message, penalty_key="manual_exception", transaction_id=None):
        item = warning(issue_type, severity, message, penalty_key, transaction_id)
        if transaction_id:
            evidence_record = evidence_records.get(transaction_id) if severity == "flag" else None
            correction_note = corrected_transactions.get(transaction_id) if severity != "flag" else None
            review_contact = review_contacts.get(transaction_id) if severity == "review" else None
            evidence_accepted = bool(evidence_record and evidence_record.get("accepted"))
            resolved = bool(evidence_accepted or correction_note)
            transaction_reviews[transaction_id].append(
                {
                    **item,
                    "resolved": resolved,
                    "correction_note": correction_note,
                    "evidence_record": evidence_record,
                    "review_contact": review_contact,
                    "requires_evidence": severity == "flag",
                }
            )
            if resolved:
                return
        warnings.append(item)

    for tx in client_transactions:
        if tx["direction"] == "sale":
            revenue += tx["amount"]
            output_vat += tx["vat_amount"]
        elif tx["direction"] == "purchase":
            input_vat += tx["vat_amount"]

        if tx["vat_code"] not in KNOWN_VAT_CODES:
            add_warning(
                "Unknown VAT code",
                "flag",
                f"The row is in a structured format, but VAT code '{tx['vat_code']}' is not accepted by the ledger payload. Ask the client or source ledger for a corrected VAT code before approval.",
                "unknown_vat_code",
                tx["transaction_id"],
            )
        if any("no receipt" in note.lower() for note in tx["normalization_notes"]):
            add_warning(
                "Unclear source PDF",
                "review",
                "The source PDF contains a receipt id label, but OCR could not confidently read the handwritten value. A human should inspect the PDF and enter the value; contact the client only if it is truly unreadable.",
                "missing_receipt",
                tx["transaction_id"],
            )

    for item in client_exceptions:
        if item["severity"] != "flag":
            continue

        issue_type = item["issue_type"].lower()
        penalty_key = "manual_exception"
        if "reverse" in issue_type or "foreign" in issue_type or "intra" in issue_type:
            penalty_key = "reverse_charge"

        related_transactions = related_transactions_for_exception(item["issue_type"], client_transactions)
        if related_transactions:
            for tx in related_transactions:
                add_warning(
                    item["issue_type"],
                    item["severity"],
                    f"{item['detail']} Related transaction: {tx['transaction_id']}.",
                    penalty_key,
                    tx["transaction_id"],
                )
        else:
            add_warning(item["issue_type"], item["severity"], item["detail"], penalty_key)

    vat_due = output_vat - input_vat
    has_flag = any(item["severity"] == "flag" for item in warnings)
    has_review = any(item["severity"] == "review" for item in warnings)

    if approved_payload:
        status = "Filed"
    elif client["already_filed"]:
        status = "Filed"
    elif has_flag:
        status = "Flagged"
    elif has_review:
        status = "Review"
    else:
        status = "Ready"

    confidence = confidence_for(client["client_id"], warnings)
    if status == "Filed":
        confidence = max(confidence, 94)

    open_transaction_issue_count = sum(
        1
        for items in transaction_reviews.values()
        if any(not item["resolved"] for item in items)
    )
    corrected_transaction_count = sum(
        1
        for items in transaction_reviews.values()
        if items and all(item["resolved"] for item in items)
    )

    if warnings:
        queue_note = warnings[0]["message"]
    elif corrected_transaction_count:
        queue_note = "Ready after resolved review items"
    elif approved_payload:
        queue_note = "Filed after bookkeeper approval"
    elif client["already_filed"]:
        queue_note = "Already filed in source data"
    else:
        queue_note = "Routine quarter"

    return {
        **client,
        "transactions": [
            {
                **tx,
                "receipt": transaction_receipt_field(tx, transaction_reviews.get(tx["transaction_id"], [])),
                "vat_comment": VAT_CODE_COMMENTS.get(tx["vat_code"], ""),
                "review_items": transaction_reviews.get(tx["transaction_id"], []),
                "review_status": transaction_status(transaction_reviews.get(tx["transaction_id"], [])),
                "evidence": transaction_evidence_fields(transaction_reviews.get(tx["transaction_id"], [])),
                "needs_correction": any(not item["resolved"] for item in transaction_reviews.get(tx["transaction_id"], [])),
                "correction_note": corrected_transactions.get(tx["transaction_id"], ""),
            }
            for tx in client_transactions
        ],
        "warnings": warnings,
        "status": status,
        "status_key": status_key(status),
        "confidence": confidence,
        "queue_note": queue_note,
        "can_approve": status == "Ready",
        "is_approved": bool(approved_payload),
        "approved_payload": approved_payload,
        "revenue": money(revenue),
        "input_vat": money(input_vat),
        "output_vat": money(output_vat),
        "vat_due": money(vat_due),
        "transaction_count": len(client_transactions),
        "open_transaction_issue_count": open_transaction_issue_count,
        "corrected_transaction_count": corrected_transaction_count,
        "source_transaction_ids": [tx["transaction_id"] for tx in client_transactions],
    }


def build_dashboard(data, approvals=None, corrections=None, evidence_records=None, review_contacts=None):
    approvals = approvals or {}
    corrections = corrections or {}
    evidence_records = evidence_records or {}
    review_contacts = review_contacts or {}
    clients = [
        analyze_client(
            client,
            data["transactions"],
            data["exceptions"],
            approved_payload=approvals.get(client["client_id"]),
            corrected_transactions=corrections,
            evidence_records=evidence_records,
            review_contacts=review_contacts,
        )
        for client in data["clients"]
    ]

    ledgers = sorted({client["ledger"] for client in clients})
    counts = Counter(client["status_key"] for client in clients)
    total_vat_due = sum(Decimal(str(client["vat_due"])) for client in clients)
    ready_count = counts.get("ready", 0)

    return {
        "office": data["office"],
        "clients": clients,
        "ledgers": ledgers,
        "counts": counts,
        "total_clients": len(clients),
        "ready_count": ready_count,
        "review_count": counts.get("review", 0),
        "flagged_count": counts.get("flagged", 0),
        "filed_count": counts.get("filed", 0),
        "total_vat_due": money(total_vat_due),
        "estimated_minutes_saved": ready_count * 18,
    }


def find_summary(dashboard, client_id):
    for summary in dashboard["clients"]:
        if summary["client_id"] == client_id:
            return summary
    return None