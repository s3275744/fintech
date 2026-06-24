import re
from csv import DictReader
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "profiles"


def list_profiles(data_root=DATA_ROOT):
    if not data_root.exists():
        return []
    preferred_order = {"small": 0, "medium": 1, "large": 2}
    return sorted(
        (path.name for path in data_root.iterdir() if path.is_dir()),
        key=lambda name: preferred_order.get(name, 99),
    )


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file_handle:
        return list(DictReader(file_handle))


def clean_text(value):
    return " ".join((value or "").strip().split())


def parse_bool(value):
    return clean_text(value).lower() in {"1", "yes", "true", "y"}


def parse_money(value):
    original = value or "0"
    text = clean_text(original).replace("€", "")
    text = text.replace(" ", "")

    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def parse_percent(value):
    text = clean_text(value).replace("%", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text) / Decimal("100")
    except InvalidOperation:
        return Decimal("0")


def normalize_kvk(value):
    original = clean_text(value)
    digits = re.sub(r"\D", "", original)
    if len(digits) == 8:
        return digits, original != digits
    return original, True


def normalize_client(row):
    kvk, kvk_was_messy = normalize_kvk(row.get("kvk", ""))
    return {
        "client_id": clean_text(row.get("client_id")),
        "name": clean_text(row.get("name")),
        "kvk": kvk,
        "original_kvk": clean_text(row.get("kvk")),
        "kvk_was_messy": kvk_was_messy,
        "ledger": clean_text(row.get("ledger")),
        "sector": clean_text(row.get("sector")),
        "vat_scheme": clean_text(row.get("vat_scheme")) or "standard",
        "already_filed": parse_bool(row.get("already_filed")),
        "ytd_revenue_before_q2": parse_money(row.get("ytd_revenue_before_q2")),
    }


def normalize_transaction(row):
    amount = parse_money(row.get("amount"))
    vat_amount = parse_money(row.get("vat_amount"))
    vat_rate = parse_percent(row.get("vat_rate"))
    vat_code = clean_text(row.get("vat_code")).upper()

    notes = []
    if clean_text(row.get("amount")) != str(row.get("amount", "")).strip():
        notes.append("Amount had extra whitespace and was cleaned.")
    if not clean_text(row.get("receipt_id")) and clean_text(row.get("direction")).lower() == "purchase":
        notes.append("Purchase has no receipt id.")

    return {
        "transaction_id": clean_text(row.get("transaction_id")),
        "date": clean_text(row.get("date")),
        "client_id": clean_text(row.get("client_id")),
        "direction": clean_text(row.get("direction")).lower(),
        "counterparty": clean_text(row.get("counterparty")),
        "description": clean_text(row.get("description")),
        "amount": amount,
        "vat_amount": vat_amount,
        "vat_rate": vat_rate,
        "vat_code": vat_code,
        "receipt_id": clean_text(row.get("receipt_id")),
        "source_ledger_id": clean_text(row.get("source_ledger_id")),
        "normalization_notes": notes,
    }


def normalize_exception(row):
    return {
        "client_id": clean_text(row.get("client_id")),
        "issue_type": clean_text(row.get("issue_type")),
        "severity": clean_text(row.get("severity")).lower() or "review",
        "detail": clean_text(row.get("detail")),
    }


def load_profile(profile_name, data_root=DATA_ROOT):
    profile_path = data_root / profile_name
    if not profile_path.exists():
        raise FileNotFoundError(f"Unknown profile: {profile_name}")

    office_rows = read_csv(profile_path / "office.csv")
    office = office_rows[0] if office_rows else {}
    office = {key: clean_text(value) for key, value in office.items()}
    office["profile"] = profile_name

    clients = [normalize_client(row) for row in read_csv(profile_path / "clients.csv")]
    transactions = [normalize_transaction(row) for row in read_csv(profile_path / "transactions.csv")]
    exceptions = [normalize_exception(row) for row in read_csv(profile_path / "exceptions.csv")]

    return {
        "office": office,
        "clients": clients,
        "transactions": transactions,
        "exceptions": exceptions,
    }