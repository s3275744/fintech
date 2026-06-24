from datetime import datetime, timezone
from hashlib import sha1


def money_value(value):
    return round(float(value), 2)


def receipt_value(transaction):
    receipt = transaction.get("receipt", {})
    if receipt.get("status") in {"present", "entered"}:
        return receipt.get("value")
    return None


def evidence_summary(transaction):
    evidence = transaction.get("evidence", {})
    if not evidence.get("required"):
        return {"required": False}

    result = {
        "required": True,
        "status": evidence.get("status"),
        "buyer_vat_number_evidence": evidence.get("vat_value"),
        "transport_proof_required": bool(evidence.get("transport_required")),
    }
    if evidence.get("transport_required") or evidence.get("transport_value") == "Not required":
        result["transport_proof"] = evidence.get("transport_value")
    return result


def source_transaction_payload(transaction):
    return {
        "transaction_id": transaction["transaction_id"],
        "date": transaction["date"],
        "direction": transaction["direction"],
        "counterparty": transaction["counterparty"],
        "description": transaction["description"],
        "amount_eur": money_value(transaction["amount"]),
        "vat_amount_eur": money_value(transaction["vat_amount"]),
        "vat_code": transaction["vat_code"],
        "vat_comment": transaction.get("vat_comment") or None,
        "receipt_id": receipt_value(transaction),
        "review_status": transaction.get("review_status", "clear"),
        "evidence": evidence_summary(transaction),
        "source_document_ref": f"{transaction['transaction_id']}.pdf",
    }


def review_audit(summary):
    audit_items = []
    for transaction in summary["transactions"]:
        for item in transaction.get("review_items", []):
            if not item.get("resolved"):
                continue

            if item.get("requires_evidence"):
                evidence_record = item.get("evidence_record") or {}
                audit_items.append(
                    {
                        "transaction_id": transaction["transaction_id"],
                        "issue_type": item["issue_type"],
                        "resolution": "evidence_pdf_accepted",
                        "analysis": evidence_record.get("analysis"),
                        "buyer_vat_number": evidence_record.get("buyer_vat_number"),
                        "transport_proof": evidence_record.get("transport_proof"),
                    }
                )
            else:
                audit_items.append(
                    {
                        "transaction_id": transaction["transaction_id"],
                        "issue_type": item["issue_type"],
                        "resolution": "manual_receipt_entry",
                        "entered_value": item.get("correction_note"),
                    }
                )
    return audit_items


def build_ledger_payload(office, summary):
    key_source = f"{office.get('profile')}:{summary['client_id']}:{office.get('quarter')}:{summary['vat_due']}"
    idempotency_key = sha1(key_source.encode("utf-8")).hexdigest()[:16]

    return {
        "sandbox_notice": "No external API call is made.",
        "target_ledger": summary["ledger"],
        "endpoint_example": f"POST /ledger/{summary['ledger'].lower().replace(' ', '-')}/vat-entries",
        "idempotency_key": idempotency_key,
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "approved_by": "bookkeeper@fiskal.local",
        "office": {
            "name": office.get("office_name"),
            "city": office.get("city"),
        },
        "client": {
            "client_id": summary["client_id"],
            "name": summary["name"],
            "kvk": summary["kvk"],
        },
        "quarter": office.get("quarter"),
        "vat_totals": {
            "revenue_eur": summary["revenue"],
            "output_vat_eur": summary["output_vat"],
            "input_vat_eur": summary["input_vat"],
            "vat_due_eur": summary["vat_due"],
        },
        "classification": {
            "status_before_approval": summary["status"],
            "confidence": summary["confidence"],
            "warning_count": len(summary["warnings"]),
            "warnings": [item["message"] for item in summary["warnings"]],
        },
        "approval_checks": {
            "all_transaction_issues_resolved": summary["open_transaction_issue_count"] == 0,
            "open_transaction_issue_count": summary["open_transaction_issue_count"],
            "corrected_transaction_count": summary["corrected_transaction_count"],
        },
        "source_transaction_ids": summary["source_transaction_ids"],
        "source_transactions": [source_transaction_payload(transaction) for transaction in summary["transactions"]],
        "review_audit": review_audit(summary),
        "next_step": "Ledger prepares the official SBR/Digipoort filing after the bookkeeper signs off.",
    }