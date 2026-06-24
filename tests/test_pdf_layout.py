import re

import pytest

fitz = pytest.importorskip("fitz")

from fiskal.data_loader import DATA_ROOT, list_profiles, load_profile
from fiskal.sample_pdf import build_evidence_pdf, build_sample_pdf


MONEY_PATTERN = re.compile(r"EUR [0-9,]+\.[0-9]{2}")


def generated_pdfs():
    for profile in list_profiles(DATA_ROOT):
        data = load_profile(profile)
        clients = {client["client_id"]: client for client in data["clients"]}
        for transaction in data["transactions"]:
            client = clients.get(transaction["client_id"])
            yield f"{profile}/sample/{transaction['transaction_id']}", build_sample_pdf(data["office"], client, transaction)
            if transaction["vat_code"] == "EU_REVERSE":
                yield f"{profile}/evidence/{transaction['transaction_id']}", build_evidence_pdf(
                    data["office"], client, transaction
                )


def test_generated_pdf_text_stays_inside_layout():
    violations = []

    for name, pdf in generated_pdfs():
        document = fitz.open(stream=pdf, filetype="pdf")
        page = document[0]
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                money_spans = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    x0, y0, x1, y1 = span["bbox"]
                    if x0 < -0.5 or y0 < -0.5 or x1 > page.rect.width + 0.5 or y1 > page.rect.height + 0.5:
                        violations.append(f"{name}: page bounds overflow: {span_text!r} {span['bbox']}")
                    if x0 < 38 or x1 > 557:
                        violations.append(f"{name}: content margin overflow: {span_text!r} {span['bbox']}")
                    if span_text.count("EUR ") > 1:
                        violations.append(f"{name}: merged money values: {span_text!r} {span['bbox']}")
                    if MONEY_PATTERN.search(span_text):
                        money_spans.append(span)

                money_spans.sort(key=lambda item: item["bbox"][0])
                for left, right in zip(money_spans, money_spans[1:]):
                    gap = right["bbox"][0] - left["bbox"][2]
                    if gap < 6:
                        violations.append(
                            f"{name}: money values too close: {left['text']!r} / {right['text']!r} gap={gap:.1f}"
                        )

    assert not violations, "\n".join(violations)