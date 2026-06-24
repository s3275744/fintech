from fiskal.rules import needs_transport_proof

HANDWRITTEN_RECEIPT_VALUES = {
    "S-T008": "TS 520-78416",
    "S-T018": "JUM 529-4187",
    "M-T008": "SLG 512-88421",
    "M-T040": "HF 521-7719",
    "L-T008": "KT 514-6B31",
    "L-T035": "GH 507-48192",
    "L-T070": "HOT 515-2048",
}

LEDGER_PALETTES = {
    "mb": {"accent": "0.08 0.32 0.30", "soft": "0.90 0.96 0.94", "dark": "0.06 0.18 0.20"},
    "tw": {"accent": "0.14 0.27 0.45", "soft": "0.91 0.94 0.98", "dark": "0.10 0.18 0.30"},
    "ex": {"accent": "0.42 0.18 0.28", "soft": "0.98 0.91 0.94", "dark": "0.27 0.10 0.17"},
    "sn": {"accent": "0.28 0.32 0.22", "soft": "0.94 0.96 0.89", "dark": "0.18 0.20 0.14"},
}


def palette_for(transaction):
    ledger_id = str(transaction.get("source_ledger_id", ""))
    key = ledger_id.split("-", 1)[0].lower()
    return LEDGER_PALETTES.get(key, {"accent": "0.12 0.23 0.37", "soft": "0.92 0.95 0.98", "dark": "0.10 0.16 0.24"})


def pdf_escape(value):
    text = str(value or "")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def money_text(value):
    return f"EUR {float(value):,.2f}"


def text(x, y, value, size=10, font="F1", color="0 0 0"):
    return f"BT {color} rg /{font} {size} Tf {x} {y} Td ({pdf_escape(value)}) Tj ET"


FONT_WIDTH_FACTORS = {
    "F1": 0.52,
    "F2": 0.56,
    "F3": 0.60,
}


def estimated_text_width(value, size=10, font="F1"):
    return len(str(value or "")) * float(size) * FONT_WIDTH_FACTORS.get(font, 0.54)


def fitted_font_size(value, max_width, size=10, font="F1", min_size=7):
    font_size = float(size)
    while font_size > min_size and estimated_text_width(value, font_size, font) > max_width:
        font_size -= 0.5
    return max(font_size, min_size)


def ellipsized_text(value, max_width, size=10, font="F1"):
    value = str(value or "")
    if estimated_text_width(value, size, font) <= max_width:
        return value
    max_chars = int(max_width / (float(size) * FONT_WIDTH_FACTORS.get(font, 0.54)))
    if max_chars <= 3:
        return value[:max(1, max_chars)]
    return f"{value[:max_chars - 3]}..."


def fit_text(x, y, value, size=10, font="F1", color="0 0 0", max_width=120, min_size=7):
    font_size = fitted_font_size(value, max_width, size, font, min_size)
    value = ellipsized_text(value, max_width, font_size, font)
    return text(x, y, value, round(font_size, 1), font, color)


def right_text(right_x, y, value, size=10, font="F1", color="0 0 0", min_x=42, min_size=7):
    available_width = max(1, right_x - min_x)
    font_size = fitted_font_size(value, available_width, size, font, min_size)
    value = ellipsized_text(value, available_width, font_size, font)
    x = right_x - estimated_text_width(value, font_size, font)
    return text(round(max(min_x, x), 1), y, value, round(font_size, 1), font, color)


def transformed_text(x, y, value, size=10, font="F1", color="0 0 0", matrix="1 0 0 1"):
    return f"BT {color} rg /{font} {size} Tf {matrix} {x} {y} Tm ({pdf_escape(value)}) Tj ET"


def fill_rect(x, y, width, height, color):
    return f"q {color} rg {x} {y} {width} {height} re f Q"


def stroke_rect(x, y, width, height, color="0.65 0.70 0.76"):
    return f"q {color} RG {x} {y} {width} {height} re S Q"


def line(x1, y1, x2, y2, color="0.65 0.70 0.76"):
    return f"q {color} RG {x1} {y1} m {x2} {y2} l S Q"


def total_text(transaction):
    return money_text(float(transaction["amount"]) + float(transaction["vat_amount"]))


def barcode(x, y, height=30, color="0.10 0.10 0.10"):
    widths = (2, 1, 3, 1, 2, 4, 1, 3, 2, 1, 1, 4, 2, 3, 1, 2, 4, 1, 2, 3)
    commands = []
    cursor = 0
    for index, width in enumerate(widths):
        if index % 2 == 0:
            commands.append(fill_rect(x + cursor, y, width, height, color))
        cursor += width + 2
    return commands


def qr_block(x, y, color="0.10 0.10 0.10"):
    commands = [stroke_rect(x, y, 54, 54, "0.74 0.78 0.82")]
    cells = (
        (2, 2), (3, 2), (4, 2), (2, 3), (4, 3), (2, 4), (3, 4), (4, 4),
        (8, 2), (9, 2), (10, 2), (8, 3), (10, 3), (8, 4), (9, 4), (10, 4),
        (2, 8), (3, 8), (4, 8), (2, 9), (4, 9), (2, 10), (3, 10), (4, 10),
        (6, 6), (7, 6), (9, 6), (5, 7), (8, 8), (10, 9), (6, 10), (9, 11),
    )
    for col, row in cells:
        commands.append(fill_rect(x + col * 4, y + row * 4, 3, 3, color))
    return commands


def receipt_edge(x, y, width):
    return [line(x + offset, y, x + offset + 6, y, "0.76 0.75 0.68") for offset in range(0, width - 4, 12)]


def review_receipt_value(transaction):
    if transaction.get("receipt_id"):
        return transaction["receipt_id"]
    return HANDWRITTEN_RECEIPT_VALUES.get(transaction["transaction_id"], "BON 000-0000")


def shaky_handwritten_text(x, y, value):
    commands = []
    cursor = 0
    matrices = ("0.99 0.08 -0.08 0.99", "1 -0.05 0.05 1", "0.98 0.13 -0.13 0.98", "1 0.03 -0.03 1")
    offsets = (0, 1.2, -0.8, 0.5)
    for index, char in enumerate(value):
        if char == " ":
            cursor += 7
            continue
        commands.append(
            transformed_text(
                x + cursor,
                y + offsets[index % len(offsets)],
                char,
                12,
                "F3",
                "0.31 0.31 0.34",
                matrices[index % len(matrices)],
            )
        )
        cursor += 7 if char in "-/." else 9
    return commands


def ocr_noise_box(x, y, width, height):
    return [
        fill_rect(x, y, width, height, "0.93 0.92 0.88"),
        stroke_rect(x, y, width, height, "0.62 0.60 0.55"),
        line(x + 4, y + 5, x + width - 5, y + height - 7, "0.72 0.70 0.66"),
        line(x + 7, y + height - 5, x + width - 8, y + 6, "0.78 0.76 0.70"),
        line(x + 16, y + 3, x + width - 20, y + 3, "0.80 0.78 0.72"),
    ]


def build_annotation(annotation_id, annotation):
    x = annotation.get("x", 548)
    y = annotation.get("y", 748)
    title = pdf_escape(annotation.get("title", "Fiskal note"))
    contents = pdf_escape(annotation.get("contents", ""))
    return (
        f"{annotation_id} 0 obj\n"
        f"<< /Type /Annot /Subtype /Text /Rect [{x} {y} {x + 18} {y + 18}] "
        f"/Contents ({contents}) /T ({title}) /Open false /Name /Comment >>\n"
        "endobj\n"
    ).encode("latin-1", errors="replace")


def build_pdf(commands, annotations=None):
    annotations = annotations or []
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    annotation_refs = ""
    if annotations:
        annotation_refs = " /Annots [" + " ".join(f"{index} 0 R" for index in range(8, 8 + len(annotations))) + "]"

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R /F3 6 0 R >> >> /Contents 7 0 R{annotation_refs} >>\nendobj\n".encode("latin-1"),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n",
        b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
        b"7 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n",
    ]
    objects.extend(build_annotation(index, annotation) for index, annotation in enumerate(annotations, start=8))

    pdf = [b"%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(part) for part in pdf))
        pdf.append(obj)

    xref_offset = sum(len(part) for part in pdf)
    object_count = len(objects) + 1
    xref = [f"xref\n0 {object_count}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = b"trailer\n<< /Size " + str(object_count).encode("ascii") + b" /Root 1 0 R >>\nstartxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
    return b"".join(pdf + xref + [trailer])


def sample_annotations(transaction):
    notes = [
        f"Ledger export VAT code: {transaction['vat_code']}",
    ]
    if transaction["vat_code"] == "EU_REVERSE":
        if needs_transport_proof(transaction["description"]):
            notes.append("Fiskal evidence note: buyer VAT number evidence and transport proof must be checked separately.")
        else:
            notes.append("Fiskal evidence note: buyer VAT number evidence must be checked separately.")
    if not transaction.get("receipt_id") and transaction["direction"] == "purchase":
        notes.append("Fiskal review note: receipt id label is visible, but the handwritten value has low OCR confidence.")

    return [
        {
            "title": "Fiskal analysis note",
            "contents": "\n".join(notes),
            "x": 548,
            "y": 748,
        }
    ]


def invoice_layout(office, client, transaction):
    seller = client["name"] if client else "Unknown seller"
    colors = palette_for(transaction)
    ledger_label = str(transaction.get("source_ledger_id", "source")).upper()
    commands = [
        fill_rect(0, 0, 595, 842, "0.98 0.99 1.00"),
        fill_rect(0, 792, 595, 50, colors["dark"]),
        fill_rect(0, 786, 595, 6, colors["accent"]),
        fit_text(42, 812, seller, 19, "F2", "1 1 1", 360, 13),
        text(42, 795, "VAT invoice", 10, "F1", "0.86 0.91 0.96"),
        fit_text(426, 812, transaction["transaction_id"], 14, "F2", "1 1 1", 126, 10),
        fit_text(426, 795, f"Issued {transaction['date']}", 9, "F1", "0.86 0.91 0.96", 126, 8),
        stroke_rect(42, 692, 230, 70, "0.79 0.84 0.89"),
        fill_rect(42, 744, 230, 18, colors["soft"]),
        text(54, 749, "Bill to", 9, "F2", colors["dark"]),
        fit_text(54, 724, transaction["counterparty"], 13, "F2", "0 0 0", 198, 9),
        text(54, 707, "Customer address on file", 9, "F1", "0.38 0.44 0.50"),
        stroke_rect(322, 692, 230, 70, "0.79 0.84 0.89"),
        fill_rect(322, 744, 230, 18, colors["soft"]),
        text(334, 749, "Supplier details", 9, "F2", colors["dark"]),
        fit_text(334, 724, f"KVK {client['kvk'] if client else '00000000'}", 11, "F3", "0 0 0", 198, 8),
        fit_text(334, 707, f"Ledger ref {ledger_label}", 9, "F1", "0.38 0.44 0.50", 198, 8),
        stroke_rect(42, 500, 510, 150, "0.74 0.80 0.86"),
        fill_rect(42, 620, 510, 30, colors["accent"]),
        text(56, 630, "Description", 9, "F2", "1 1 1"),
        right_text(365, 630, "Net", 9, "F2", "1 1 1", 286, 8),
        right_text(450, 630, "VAT", 9, "F2", "1 1 1", 378, 8),
        right_text(540, 630, "Total", 9, "F2", "1 1 1", 462, 8),
        fit_text(56, 596, transaction["description"], 10, "F1", "0 0 0", 220, 8),
        right_text(365, 596, money_text(transaction["amount"]), 10, "F3", "0 0 0", 286, 8),
        right_text(450, 596, money_text(transaction["vat_amount"]), 10, "F3", "0 0 0", 378, 8),
        right_text(540, 596, total_text(transaction), 10, "F3", "0 0 0", 462, 8),
        line(54, 572, 540, 572, "0.82 0.86 0.90"),
        text(56, 548, f"VAT code {transaction['vat_code']}", 9, "F2", colors["accent"]),
        text(56, 530, "Payment due according to the quarter close agreement", 8, "F1", "0.38 0.44 0.50"),
        fill_rect(352, 416, 200, 64, colors["soft"]),
        stroke_rect(352, 416, 200, 64, "0.74 0.80 0.86"),
        text(366, 456, "Amount payable", 10, "F2", colors["dark"]),
        fit_text(366, 435, total_text(transaction), 18, "F2", colors["accent"], 172, 12),
        stroke_rect(42, 406, 250, 84, "0.79 0.84 0.89"),
        text(56, 462, "Payment reference", 9, "F2", colors["dark"]),
        fit_text(56, 442, transaction["receipt_id"], 11, "F3", "0 0 0", 220, 8),
        text(56, 422, "IBAN on file with administration", 8, "F1", "0.38 0.44 0.50"),
        *barcode(42, 112, 34, colors["dark"]),
        fit_text(42, 92, f"Exported from {ledger_label} for Q2 2026 VAT review", 8, "F1", "0.42 0.47 0.53", 510, 7),
        line(42, 82, 552, 82, "0.82 0.86 0.90"),
        fit_text(42, 62, office.get("office_name", "Fiskal office"), 8, "F2", colors["dark"], 145, 7),
        text(202, 62, "Source invoice stored in client ledger", 8, "F1", "0.42 0.47 0.53"),
    ]
    return commands


def receipt_layout(office, client, transaction):
    receipt_value = review_receipt_value(transaction)
    receipt_total = total_text(transaction)
    ledger_label = str(transaction.get("source_ledger_id", "source")).upper()
    receipt_commands = []
    if transaction["receipt_id"]:
        receipt_commands.extend(
            [
                text(190, 626, "Receipt id:", 9, "F2"),
                fit_text(280, 626, receipt_value, 10, "F3", "0 0 0", 124, 8),
            ]
        )
    else:
        receipt_commands.extend(
            [
                text(190, 626, "Receipt id:", 9, "F2"),
                fill_rect(274, 613, 130, 25, "0.96 0.94 0.86"),
                *ocr_noise_box(274, 613, 130, 25),
                *shaky_handwritten_text(282, 621, receipt_value),
                text(190, 604, "written on counter slip", 7, "F1", "0.46 0.45 0.40"),
            ]
        )

    commands = [
        fill_rect(0, 0, 595, 842, "0.95 0.96 0.94"),
        fill_rect(158, 56, 282, 724, "0.82 0.82 0.76"),
        fill_rect(152, 64, 282, 724, "0.99 0.98 0.91"),
        *receipt_edge(152, 788, 282),
        *receipt_edge(152, 64, 282),
        stroke_rect(152, 64, 282, 724, "0.70 0.69 0.62"),
        fill_rect(174, 724, 238, 34, "0.12 0.12 0.12"),
        fit_text(190, 736, transaction["counterparty"].upper(), 14, "F2", "1 1 1", 210, 9),
        text(206, 706, "PURCHASE RECEIPT", 10, "F2", "0.28 0.27 0.24"),
        text(190, 688, "Customer copy", 8, "F1", "0.46 0.45 0.40"),
        line(184, 672, 410, 672, "0.55 0.54 0.48"),
        text(190, 652, f"Date: {transaction['date']}", 9, "F3"),
        text(312, 652, "Time: 14:38", 9, "F3"),
        *receipt_commands,
        line(184, 588, 410, 588, "0.55 0.54 0.48"),
        fit_text(190, 564, transaction["description"], 10, "F1", "0 0 0", 220, 8),
        text(190, 544, "1 x", 9, "F3"),
        right_text(410, 544, money_text(transaction["amount"]), 9, "F3", "0 0 0", 246, 8),
        text(190, 522, f"VAT {transaction['vat_code']}", 9),
        right_text(410, 522, money_text(transaction["vat_amount"]), 9, "F3", "0 0 0", 314, 8),
        line(184, 500, 410, 500, "0.55 0.54 0.48"),
        text(190, 476, "TOTAL", 12, "F2"),
        right_text(410, 476, receipt_total, 12, "F2", "0 0 0", 280, 9),
        text(190, 452, "Paid by card", 10, "F2"),
        text(190, 434, "Terminal 03   Auth 684921", 8, "F3", "0.38 0.37 0.33"),
        fit_text(190, 412, f"Ledger ref {ledger_label}", 8, "F1", "0.46 0.45 0.40", 220, 7),
        *barcode(190, 346, 38),
        text(210, 326, "Thank you, keep this receipt", 8, "F2", "0.28 0.27 0.24"),
        fit_text(198, 306, office.get("office_name", "Fiskal office"), 7, "F1", "0.46 0.45 0.40", 220, 6),
    ]
    return commands


def build_sample_pdf(office, client, transaction):
    if transaction["direction"] == "purchase":
        commands = receipt_layout(office, client, transaction)
    else:
        commands = invoice_layout(office, client, transaction)
    return build_pdf(commands, sample_annotations(transaction))


def build_evidence_pdf(office, client, transaction):
    client_name = client["name"] if client else "Unknown client"
    include_transport = needs_transport_proof(transaction["description"])
    title = "Transport and VAT evidence" if include_transport else "VAT evidence"
    subject = "Missing VAT evidence and transport proof" if include_transport else "Missing VAT evidence"
    analysis_lines = (
        ("VAT number and transport reference are readable.", "Expected formats matched for Q2 review.")
        if include_transport
        else ("Buyer VAT number is readable.", "Expected format matched for Q2 review.")
    )
    commands = [
        fill_rect(0, 0, 595, 842, "0.97 0.99 0.98"),
        fill_rect(0, 786, 595, 56, "0.10 0.33 0.26"),
        fill_rect(0, 778, 595, 8, "0.33 0.68 0.50"),
        fit_text(42, 810, title, 18, "F2", "1 1 1", 350, 12),
        fit_text(42, 792, f"Client reply package for {transaction['transaction_id']}", 10, "F1", "0.88 0.96 0.91", 350, 8),
        text(418, 810, "Evidence PDF", 11, "F2", "1 1 1"),
        stroke_rect(42, 650, 510, 92, "0.72 0.81 0.76"),
        fill_rect(42, 724, 510, 18, "0.90 0.97 0.93"),
        text(58, 729, "Email summary", 9, "F2", "0.10 0.33 0.26"),
        text(60, 704, "From", 10, "F2"),
        fit_text(120, 704, client_name, 11, "F1", "0 0 0", 410, 8),
        text(60, 682, "To", 10, "F2"),
        fit_text(120, 682, office.get("office_name"), 11, "F1", "0 0 0", 410, 8),
        text(60, 660, "Subject", 10, "F2"),
        fit_text(120, 660, subject, 11, "F1", "0 0 0", 410, 8),
        fill_rect(42, 562, 510, 58, "0.90 0.97 0.93"),
        text(60, 596, "Extracted evidence", 11, "F2", "0.10 0.33 0.26"),
        fit_text(60, 576, "Buyer VAT number: BE 0731.445.221", 10, "F3", "0 0 0", 220, 8),
        *( [fit_text(308, 576, "Transport proof: CMR-2026-Q2-118", 10, "F3", "0 0 0", 222, 8)] if include_transport else [] ),
        stroke_rect(42, 406, 320, 112, "0.72 0.81 0.76"),
        text(60, 490, "Document analysis", 11, "F2", "0.10 0.33 0.26"),
        text(60, 468, analysis_lines[0], 9),
        text(60, 450, analysis_lines[1], 9),
        text(60, 432, "The flagged row can now move to Ready.", 9),
        fit_text(60, 414, f"Related transaction: {transaction['transaction_id']} ({transaction['counterparty']})", 9, "F3", "0 0 0", 285, 7),
        stroke_rect(392, 406, 160, 112, "0.72 0.81 0.76"),
        text(410, 490, "Verification code", 10, "F2", "0.10 0.33 0.26"),
        *qr_block(414, 426, "0.10 0.33 0.26"),
        text(410, 414, "EV-Q2-2026", 8, "F3", "0.38 0.44 0.42"),
        fill_rect(42, 320, 510, 38, "0.10 0.33 0.26"),
        text(58, 334, "Status: Evidence attached and readable", 12, "F2", "1 1 1"),
        text(42, 82, "Fiskal sandbox evidence preview - no external API call is made", 8, "F1", "0.38 0.44 0.42"),
        line(42, 72, 552, 72, "0.72 0.81 0.76"),
    ]
    return build_pdf(commands)