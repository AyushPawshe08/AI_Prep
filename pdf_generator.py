import io
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

def _pdf_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _pdf_inline(text: str) -> str:
    """Converts a line of markdown (bold/italic/inline-code) into XML markup
    that reportlab's Paragraph understands."""
    text = _pdf_escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    return text

def _pdf_styles():
    base = getSampleStyleSheet()
    black = colors.black
    return {
        "DocTitle": ParagraphStyle("DocTitle", parent=base["Title"], textColor=black, fontSize=24, leading=28),
        "DocMeta": ParagraphStyle("DocMeta", parent=base["Normal"], textColor=colors.HexColor("#444444"), fontSize=9.5, leading=13),
        "SectionTitle": ParagraphStyle("SectionTitle", parent=base["Heading1"], textColor=black, fontSize=15, leading=19, spaceBefore=6, spaceAfter=8, fontName="Helvetica-Bold"),
        "H1": ParagraphStyle("H1", parent=base["Heading2"], textColor=black, fontSize=13, leading=16, spaceBefore=10, spaceAfter=5, fontName="Helvetica-Bold"),
        "H2": ParagraphStyle("H2", parent=base["Heading3"], textColor=black, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold"),
        "H3": ParagraphStyle("H3", parent=base["Heading4"], textColor=black, fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=4, fontName="Helvetica-Bold"),
        "H4": ParagraphStyle("H4", parent=base["Heading4"], textColor=black, fontSize=10, leading=13, spaceBefore=5, spaceAfter=3, fontName="Helvetica-Bold"),
        "Body": ParagraphStyle("Body", parent=base["Normal"], textColor=black, fontSize=10.2, leading=15, fontName="Helvetica"),
        "Bullet": ParagraphStyle("Bullet", parent=base["Normal"], textColor=black, fontSize=10.2, leading=15, leftIndent=14, fontName="Helvetica"),
        "Code": ParagraphStyle("Code", parent=base["Normal"], textColor=black, fontSize=8.4, leading=11, fontName="Courier"),
        "TableCell": ParagraphStyle("TableCell", parent=base["Normal"], textColor=black, fontSize=8.8, leading=12, fontName="Helvetica"),
    }

def _markdown_to_flowables(md_text: str, styles: dict) -> list:
    flowables = []
    if not (md_text and md_text.strip()):
        return flowables

    segments = re.split(r"(```[a-zA-Z]*\n.*?```)", md_text, flags=re.DOTALL)

    for seg in segments:
        if seg.startswith("```"):
            code = re.sub(r"^```[a-zA-Z]*\n", "", seg)
            code = re.sub(r"```$", "", code).rstrip("\n")
            flowables.append(Spacer(1, 4))
            flowables.append(Preformatted(code, styles["Code"]))
            flowables.append(Spacer(1, 8))
            continue

        buf: list = []
        table_buf: list = []

        def flush_buf():
            if buf:
                para_text = " ".join(buf).strip()
                if para_text:
                    flowables.append(Paragraph(_pdf_inline(para_text), styles["Body"]))
                    flowables.append(Spacer(1, 6))
                buf.clear()

        def flush_table():
            if table_buf:
                rows = []
                for r in table_buf:
                    cells = [c.strip() for c in r.strip().strip("|").split("|")]
                    if all(re.match(r"^:?-+:?$", c) for c in cells if c != ""):
                        continue
                    rows.append([Paragraph(_pdf_inline(c), styles["TableCell"]) for c in cells])
                if rows:
                    t = Table(rows, hAlign="LEFT")
                    t.setStyle(
                        TableStyle(
                            [
                                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]
                        )
                    )
                    flowables.append(t)
                    flowables.append(Spacer(1, 8))
                table_buf.clear()

        for line in seg.split("\n"):
            stripped = line.strip()

            if not stripped:
                flush_buf()
                flush_table()
                continue

            if stripped.count("|") >= 2:
                flush_buf()
                table_buf.append(stripped)
                continue
            else:
                flush_table()

            heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
            if heading:
                flush_buf()
                level = len(heading.group(1))
                style_name = {1: "H1", 2: "H2", 3: "H3", 4: "H4"}.get(level, "H4")
                flowables.append(Paragraph(_pdf_inline(heading.group(2)), styles[style_name]))
                continue

            if re.match(r"^[-*]\s+", stripped):
                flush_buf()
                item = re.sub(r"^[-*]\s+", "", stripped)
                flowables.append(Paragraph("&bull;&nbsp;&nbsp;" + _pdf_inline(item), styles["Bullet"]))
                continue

            numbered = re.match(r"^(\d+)[\.\)]\s+(.*)$", stripped)
            if numbered:
                flush_buf()
                flowables.append(
                    Paragraph(f"{numbered.group(1)}.&nbsp; " + _pdf_inline(numbered.group(2)), styles["Bullet"])
                )
                continue

            if re.match(r"^-{3,}$", stripped):
                flush_buf()
                flowables.append(Spacer(1, 4))
                continue

            buf.append(stripped)

        flush_buf()
        flush_table()

    return flowables

def build_pdf_bytes(result: dict, topic: str) -> bytes:
    """Renders every field from the pipeline's response into a single
    white-background, black-text PDF."""
    styles = _pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        title=f"{topic} — Learning Module",
    )

    story = []
    story.append(Paragraph("AI Learning Module", styles["DocMeta"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(_pdf_inline(topic or "Untitled Topic"), styles["DocTitle"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    story.append(Spacer(1, 14))

    sections = [
        ("01 — Learning Objectives", result.get("learning_objectives", "")),
        ("02 — Explanation", result.get("explanation", "")),
        ("03 — Analogy", result.get("analogy", "")),
        ("04 — Technical Explanation", result.get("technical_explanation", "")),
        ("05 — Code Example", result.get("code_example", "")),
        ("06 — Quiz", result.get("quiz", "")),
        ("07 — Answer Key", result.get("answers", "")),
        ("08 — Quick Revision", result.get("revision_notes", "")),
    ]

    for i, (title, content) in enumerate(sections):
        story.append(Paragraph(_pdf_inline(title), styles["SectionTitle"]))
        story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#999999")))
        story.append(Spacer(1, 8))
        story.extend(_markdown_to_flowables(content, styles))
        if i < len(sections) - 1:
            story.append(Spacer(1, 10))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(letter[0] / 2, 0.5 * inch, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
