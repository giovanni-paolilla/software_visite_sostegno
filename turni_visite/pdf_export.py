import logging
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .config import (
    TITLE_TEXT, PDF_FILENAME, PDF_MARGINS, ROWS_THRESHOLD_TIGHT,
    HEADER_FONT, BODY_FONT, PADDING,
    HEADER_FONT_TIGHT, BODY_FONT_TIGHT, PADDING_TIGHT,
)
from .weeks import slot_label_with_month


def _make_header_footer(title_text: str, generated_at: str):
    def _header_footer(canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 9)
        w, h = doc.pagesize
        canv.drawString(40, h - 30, title_text)
        canv.drawString(40, 25, f"Generato il {generated_at}")
        canv.drawRightString(w - 40, 25, f"Pag. {canv.getPageNumber()}")
        canv.restoreState()
    return _header_footer


def _make_table_compact(
    data,
    col_widths=None,
    header_font: int = HEADER_FONT,
    body_font: int = BODY_FONT,
    padding: int = PADDING,
) -> Table:
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONT",         (0, 0), (-1, 0),  "Helvetica-Bold", header_font),
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.lightgrey),
        ("FONT",         (0, 1), (-1, -1), "Helvetica", body_font),
        ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING",   (0, 0), (-1, -1), padding),
    ]))
    return t


def export_pdf_mesi(
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
    week_windows: dict,
    output_path: str | None = None,
) -> None:
    """
    Esporta il piano in PDF formato A4.

    Args:
        output_path: percorso di destinazione. Se None usa PDF_FILENAME da config.
    """
    if not solution or "by_month" not in solution or not solution["by_month"]:
        logging.warning("Nessuna soluzione da esportare in PDF.")
        return

    dest = output_path or PDF_FILENAME

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "TitleCustom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        spaceAfter=6,
        spaceBefore=0,
    )
    style_h2 = ParagraphStyle(
        "H2Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceBefore=4,
        spaceAfter=4,
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    story = []

    for idx, mese in enumerate(sorted(mesi)):
        blocco = solution["by_month"].get(mese)
        if not blocco:
            continue

        fam_rows_count = 1 + len(blocco["by_family"])
        bro_rows_count = 1 + sum(len(fams) for fams in blocco["by_brother"].values())

        if fam_rows_count + bro_rows_count > ROWS_THRESHOLD_TIGHT:
            hf, bf, pad = HEADER_FONT_TIGHT, BODY_FONT_TIGHT, PADDING_TIGHT
        else:
            hf, bf, pad = HEADER_FONT, BODY_FONT, PADDING

        if idx > 0:
            story.append(PageBreak())

        story.append(Paragraph(f"Mese {mese}", style_title))
        story.append(Spacer(1, 4))

        # Tabella per famiglia
        fam_rows = [["Famiglia", "Frequenza (mese)", "Fratelli assegnati (con settimana)"]]
        for fam in sorted(blocco["by_family"].keys()):
            fr_list = blocco["by_family"][fam]
            freq = frequenze.get(fam, 2)
            items = [
                f"{fr} [{slot_label_with_month(mese, freq, k, week_windows)}]"
                for k, fr in enumerate(fr_list)
            ]
            fam_rows.append([fam, str(freq), "; ".join(items)])
        story.append(_make_table_compact(fam_rows, header_font=hf, body_font=bf, padding=pad))
        story.append(Spacer(1, 4))

        # Tabella per fratello (una riga per ogni assegnazione)
        bro_table = [["Data di visita", "Fratello", "Famiglia"]]
        for fr in sorted(blocco["by_brother"].keys()):
            for fam in (blocco["by_brother"][fr] or []):
                fr_list = blocco["by_family"][fam]
                k_found = next(
                    (k for k, name in enumerate(fr_list) if name == fr),
                    None,
                )
                if k_found is not None:
                    freq = frequenze.get(fam, 2)
                    lab = slot_label_with_month(mese, freq, k_found, week_windows)
                    bro_table.append([lab, fr, fam])
                else:
                    bro_table.append(["", fr, fam])

        page_width = A4[0] - (PDF_MARGINS["left"] + PDF_MARGINS["right"])
        w_data = 0.22 * page_width
        w_fr   = 0.34 * page_width
        w_fam  = 0.44 * page_width

        story.append(Paragraph("Visite per Fratello", style_h2))
        story.append(
            _make_table_compact(
                bro_table,
                col_widths=[w_data, w_fr, w_fam],
                header_font=hf, body_font=bf, padding=pad,
            )
        )
        story.append(Spacer(1, 2))

    try:
        doc = SimpleDocTemplate(
            dest,
            pagesize=A4,
            leftMargin=PDF_MARGINS["left"],
            rightMargin=PDF_MARGINS["right"],
            topMargin=PDF_MARGINS["top"],
            bottomMargin=PDF_MARGINS["bottom"],
            title=TITLE_TEXT,
        )
        cb = _make_header_footer(TITLE_TEXT, generated_at)
        doc.build(story, onFirstPage=cb, onLaterPages=cb)
        logging.info("PDF creato: %s", dest)
    except OSError as e:
        logging.error("Errore salvataggio PDF '%s': %s", dest, e)
        raise
