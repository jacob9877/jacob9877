from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.breast_cancer_patient_models import FEATURE_NAMES, GetPatientResponse


def _header_footer(canvas: Canvas, doc):
    width, height = LETTER

    # Header bar
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#319795"))
    canvas.rect(0, height - 0.6 * inch, width, 0.6 * inch, fill=1, stroke=0)

    # App name (left)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(0.5 * inch, height - 0.4 * inch, "AI for Medical Outcomes")

    # Date (right)
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(
        width - 0.5 * inch, height - 0.4 * inch, datetime.now().strftime("%b %d, %Y")
    )

    canvas.restoreState()


def _section_title(text: str) -> Table:
    """A pill-style section header bar."""
    bar = Table([[text]], colWidths=[7.5 * inch])
    bar.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#f1f5f9"),
                ),  # slate-100
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#0f172a"),
                ),  # slate-900
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),  # slate-300
                ("ROUNDEDCORNERS", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return bar


def _kv_table(pairs: list[tuple[str, str | None]]) -> Table:
    tbl = Table(pairs, colWidths=[2.0 * inch, 5.5 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("LEADING", (0, 0), (-1, -1), 14),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),  # keys
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0f172a")),  # values
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#e2e8f0"),
                ),  # slate-200
            ]
        )
    )
    return tbl


def _fmt(val, suffix: str = "") -> str | None:
    if val is None:
        return None
    if isinstance(val, float):
        return f"{val:.2f}{suffix}"
    return f"{val}{suffix}"


def build_patient_report_pdf(patient: GetPatientResponse, patient_title: str) -> bytes:
    buf = BytesIO()

    title = f"Breast Cancer Patient Report: {patient_title}"
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=1.1 * inch,
        bottomMargin=0.8 * inch,
        title=title,
        author="AI for Medical Outcomes",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#0f172a"),  # slate-900
        spaceAfter=12,
    )

    # Title block
    flow = []
    flow.append(Paragraph(title, title_style))
    flow.append(Spacer(1, 6))

    # Demographics
    flow.append(_section_title("Demographics"))
    flow.append(Spacer(1, 6))

    demo_pairs = [
        ("Age", _fmt(patient.Age, " yrs")),
        ("Height", _fmt(patient.Height, " cm")),
        ("Weight", _fmt(patient.Weight, " kg")),
        ("BMI", _fmt(patient.BMI)),
        ("Sex", patient.Sex or None),
    ]
    flow.append(_kv_table(demo_pairs))
    flow.append(Spacer(1, 12))

    # Features
    flow.append(_section_title("Features"))
    flow.append(Spacer(1, 6))

    feat_pairs = list(patient.model_dump(include=FEATURE_NAMES).items())
    flow.append(_kv_table(feat_pairs))
    flow.append(Spacer(1, 12))

    # Diagnosis
    flow.append(_section_title("Diagnosis"))
    flow.append(Spacer(1, 6))

    diag_color = (
        colors.HexColor("#16a34a")
        if patient.diagnosis == 0
        else colors.HexColor("#dc2626")
    )
    diag_style = ParagraphStyle(
        "Diag",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=diag_color,
        spaceAfter=6,
    )
    flow.append(
        Paragraph(f"Diagnosis: {patient.get_diagnosis_text().capitalize()}", diag_style)
    )
    flow.append(Spacer(1, 3))

    doc.build(flow, onFirstPage=_header_footer, onLaterPages=_header_footer)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
