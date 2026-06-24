import os

from fiskal.data_loader import DATA_ROOT, list_profiles, load_profile
from fiskal.payloads import build_ledger_payload
from fiskal.rules import build_dashboard, find_summary, needs_transport_proof
from fiskal.sample_pdf import build_evidence_pdf, build_sample_pdf, review_receipt_value
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fiskal-demo-secret-key")


@app.template_filter("money")
def format_money(value):
    return f"{float(value):,.2f}"


@app.template_filter("whole_number")
def format_whole_number(value):
    return f"{int(value):,}"


def get_profile_name():
    profile = request.values.get("profile", "small")
    profiles = list_profiles(DATA_ROOT)
    if profile not in profiles:
        return "small"
    return profile


def get_approvals():
    return session.setdefault("approvals", {})


def get_corrections():
    return session.setdefault("corrections", {})


def get_evidence_records():
    return session.setdefault("evidence_records", {})


def get_review_contacts():
    return session.setdefault("review_contacts", {})


def review_reply_value(transaction):
    if transaction.get("direction") == "purchase":
        return review_receipt_value(transaction)
    return f"Confirmed value for {transaction['transaction_id']}"


def find_transaction(profile_name, transaction_id):
    data = load_profile(profile_name)
    return next((tx for tx in data["transactions"] if tx["transaction_id"] == transaction_id), None)


@app.get("/")
def index():
    profile_name = get_profile_name()
    status_filter = request.args.get("status", "all")
    ledger_filter = request.args.get("ledger", "all")
    search = request.args.get("q", "").strip()

    data = load_profile(profile_name)
    approvals = get_approvals().get(profile_name, {})
    corrections = get_corrections().get(profile_name, {})
    evidence_records = get_evidence_records().get(profile_name, {})
    review_contacts = get_review_contacts().get(profile_name, {})
    dashboard = build_dashboard(data, approvals, corrections, evidence_records, review_contacts)

    rows = dashboard["clients"]
    if status_filter != "all":
        rows = [row for row in rows if row["status_key"] == status_filter]
    if ledger_filter != "all":
        rows = [row for row in rows if row["ledger"] == ledger_filter]
    if search:
        search_lower = search.lower()
        rows = [
            row
            for row in rows
            if search_lower in row["name"].lower()
            or search_lower in row["kvk"].lower()
            or search_lower in row["client_id"].lower()
        ]

    return render_template(
        "index.html",
        profiles=list_profiles(DATA_ROOT),
        active_profile=profile_name,
        dashboard=dashboard,
        rows=rows,
        status_filter=status_filter,
        ledger_filter=ledger_filter,
        search=search,
    )


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "app": "fiskal"})


@app.get("/client/<profile_name>/<client_id>")
def client_detail(profile_name, client_id):
    if profile_name not in list_profiles(DATA_ROOT):
        return redirect(url_for("index"))

    data = load_profile(profile_name)
    approvals = get_approvals().get(profile_name, {})
    corrections = get_corrections().get(profile_name, {})
    evidence_records = get_evidence_records().get(profile_name, {})
    review_contacts = get_review_contacts().get(profile_name, {})
    dashboard = build_dashboard(data, approvals, corrections, evidence_records, review_contacts)
    summary = find_summary(dashboard, client_id)
    if not summary:
        return redirect(url_for("index", profile=profile_name))

    payload = None
    if summary["is_approved"]:
        payload = summary["approved_payload"]
    elif summary["can_approve"]:
        payload = build_ledger_payload(data["office"], summary)
    return render_template(
        "client.html",
        profiles=list_profiles(DATA_ROOT),
        active_profile=profile_name,
        office=data["office"],
        summary=summary,
        payload=payload,
    )


@app.post("/approve")
def approve_clients():
    profile_name = get_profile_name()
    selected_ids = request.form.getlist("client_id")
    data = load_profile(profile_name)
    approvals = get_approvals()
    corrections = get_corrections().get(profile_name, {})
    evidence_records = get_evidence_records().get(profile_name, {})
    review_contacts = get_review_contacts().get(profile_name, {})
    profile_approvals = approvals.setdefault(profile_name, {})
    dashboard = build_dashboard(data, profile_approvals, corrections, evidence_records, review_contacts)

    approved = []
    blocked = []
    for client_id in selected_ids:
        summary = find_summary(dashboard, client_id)
        if not summary:
            continue
        if summary["can_approve"]:
            payload = build_ledger_payload(data["office"], summary)
            profile_approvals[client_id] = payload
            approved.append(client_id)
        else:
            blocked.append(client_id)

    session["approvals"] = approvals
    session["last_action"] = {"approved": approved, "blocked": blocked}
    return redirect(url_for("index", profile=profile_name))


@app.post("/correct-transaction")
def correct_transaction():
    profile_name = get_profile_name()
    client_id = request.form.get("client_id", "")
    transaction_id = request.form.get("transaction_id", "")
    correction_note = request.form.get("correction_note", "").strip()

    if correction_note and transaction_id:
        corrections = get_corrections()
        profile_corrections = corrections.setdefault(profile_name, {})
        profile_corrections[transaction_id] = correction_note
        session["corrections"] = corrections
        session["last_action"] = {"approved": [], "blocked": [], "corrected": [transaction_id]}

    return redirect(url_for("client_detail", profile_name=profile_name, client_id=client_id))


@app.post("/request-review-help")
def request_review_help():
    profile_name = get_profile_name()
    client_id = request.form.get("client_id", "")
    transaction_id = request.form.get("transaction_id", "")
    issue_type = request.form.get("issue_type", "unclear source PDF")

    if transaction_id:
        data = load_profile(profile_name)
        transaction = next(
            (tx for tx in data["transactions"] if tx["transaction_id"] == transaction_id),
            None,
        )
        confirmed_value = review_reply_value(transaction) if transaction else f"Confirmed value for {transaction_id}"
        review_contacts = get_review_contacts()
        profile_contacts = review_contacts.setdefault(profile_name, {})
        profile_contacts[transaction_id] = {
            "subject": f"Please confirm value for {transaction_id}",
            "request": f"Hi, we checked the source PDF but the value for {issue_type} is still unreadable. Can you confirm the value or send a clearer copy?",
            "reply": f"The value is {confirmed_value}. It was handwritten on the original document, so the scan can be hard to read.",
            "confirmed_value": confirmed_value,
        }
        session["review_contacts"] = review_contacts
        session["last_action"] = {"approved": [], "blocked": [], "review_contacted": [transaction_id]}

    return redirect(url_for("client_detail", profile_name=profile_name, client_id=client_id))


@app.post("/use-review-reply")
def use_review_reply():
    profile_name = get_profile_name()
    client_id = request.form.get("client_id", "")
    transaction_id = request.form.get("transaction_id", "")

    contact = get_review_contacts().get(profile_name, {}).get(transaction_id)
    if contact and transaction_id:
        corrections = get_corrections()
        profile_corrections = corrections.setdefault(profile_name, {})
        profile_corrections[transaction_id] = contact["confirmed_value"]
        session["corrections"] = corrections
        session["last_action"] = {"approved": [], "blocked": [], "corrected": [transaction_id]}

    return redirect(url_for("client_detail", profile_name=profile_name, client_id=client_id))


@app.post("/request-evidence")
def request_evidence():
    profile_name = get_profile_name()
    client_id = request.form.get("client_id", "")
    transaction_id = request.form.get("transaction_id", "")
    issue_type = request.form.get("issue_type", "missing evidence")

    if transaction_id:
        transaction = find_transaction(profile_name, transaction_id)
        include_transport = transaction and needs_transport_proof(issue_type, transaction.get("description"))
        request_detail = "Please send the buyer VAT-number evidence and transport proof." if include_transport else "Please send the buyer VAT-number evidence or corrected source document."
        reply_detail = "the VAT number and transport proof" if include_transport else "the buyer VAT-number evidence"
        evidence_records = get_evidence_records()
        profile_evidence = evidence_records.setdefault(profile_name, {})
        profile_evidence[transaction_id] = {
            "subject": f"Missing evidence for {transaction_id}",
            "request": f"Hi, we are missing support for: {issue_type}. {request_detail}",
            "reply": f"Thanks, attached is the corrected evidence PDF with {reply_detail}. Please use this for the Q2 BTW check.",
            "analysis": "Fiskal analysed the new PDF and found the missing evidence in the expected format.",
            "buyer_vat_number": "",
            "transport_proof": "",
            "accepted": False,
        }
        session["evidence_records"] = evidence_records
        session["last_action"] = {"approved": [], "blocked": [], "evidence": [transaction_id]}

    return redirect(url_for("client_detail", profile_name=profile_name, client_id=client_id))


@app.post("/analyse-evidence")
def analyse_evidence():
    profile_name = get_profile_name()
    client_id = request.form.get("client_id", "")
    transaction_id = request.form.get("transaction_id", "")

    if transaction_id:
        transaction = find_transaction(profile_name, transaction_id)
        include_transport = transaction and needs_transport_proof(transaction.get("description"))
        evidence_records = get_evidence_records()
        profile_evidence = evidence_records.setdefault(profile_name, {})
        record = profile_evidence.setdefault(
            transaction_id,
            {
                "subject": f"Missing evidence for {transaction_id}",
                "request": "Please send the missing compliance evidence for this transaction.",
                "reply": "Attached is the corrected evidence PDF.",
                "analysis": "Fiskal analysed the new PDF and found the missing evidence in the expected format.",
            },
        )
        record["buyer_vat_number"] = "BE 0731.445.221"
        record["transport_proof"] = "CMR-2026-Q2-118" if include_transport else ""
        record["accepted"] = True
        session["evidence_records"] = evidence_records
        session["last_action"] = {"approved": [], "blocked": [], "evidence_analysed": [transaction_id]}

    return redirect(url_for("client_detail", profile_name=profile_name, client_id=client_id))


@app.post("/reset")
def reset_demo():
    session.pop("approvals", None)
    session.pop("corrections", None)
    session.pop("evidence_records", None)
    session.pop("review_contacts", None)
    session.pop("last_action", None)
    next_path = request.form.get("next", "")
    if next_path.startswith("/") and not next_path.startswith("//"):
        return redirect(next_path)
    return redirect(url_for("index", profile=get_profile_name()))


@app.get("/api/payload/<profile_name>/<client_id>")
def payload_api(profile_name, client_id):
    if profile_name not in list_profiles(DATA_ROOT):
        return jsonify({"error": "Unknown profile"}), 404

    data = load_profile(profile_name)
    approvals = get_approvals().get(profile_name, {})
    corrections = get_corrections().get(profile_name, {})
    evidence_records = get_evidence_records().get(profile_name, {})
    review_contacts = get_review_contacts().get(profile_name, {})
    dashboard = build_dashboard(data, approvals, corrections, evidence_records, review_contacts)
    summary = find_summary(dashboard, client_id)
    if not summary:
        return jsonify({"error": "Unknown client"}), 404

    payload = build_ledger_payload(data["office"], summary)
    return jsonify(
        {
            "sandbox": True,
            "message": "No external API call was made.",
            "can_approve": summary["can_approve"],
            "status": summary["status"],
            "payload": payload,
        }
    )


@app.get("/sample-document/<profile_name>/<transaction_id>.pdf")
def sample_document(profile_name, transaction_id):
    if profile_name not in list_profiles(DATA_ROOT):
        return "Unknown profile", 404

    data = load_profile(profile_name)
    transaction = next(
        (tx for tx in data["transactions"] if tx["transaction_id"] == transaction_id),
        None,
    )
    if not transaction:
        return "Unknown transaction", 404

    client = next(
        (item for item in data["clients"] if item["client_id"] == transaction["client_id"]),
        None,
    )
    pdf = build_sample_pdf(data["office"], client, transaction)
    filename = f"{transaction_id}.pdf"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@app.get("/evidence-document/<profile_name>/<transaction_id>.pdf")
def evidence_document(profile_name, transaction_id):
    if profile_name not in list_profiles(DATA_ROOT):
        return "Unknown profile", 404

    data = load_profile(profile_name)
    transaction = next(
        (tx for tx in data["transactions"] if tx["transaction_id"] == transaction_id),
        None,
    )
    if not transaction:
        return "Unknown transaction", 404

    client = next(
        (item for item in data["clients"] if item["client_id"] == transaction["client_id"]),
        None,
    )
    pdf = build_evidence_pdf(data["office"], client, transaction)
    filename = f"{transaction_id}-evidence.pdf"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)