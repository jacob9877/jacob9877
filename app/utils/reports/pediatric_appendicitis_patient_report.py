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

from app.models.pediatric_appendicitis_patient_models import FEATURE_NAMES, GetPatientResponse


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
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),  # slate-300
                ("ROUNDEDCORNERS", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return bar


def _kv_table(pairs: list[tuple[str, str | None]]) -> Table:
    tbl = Table(pairs, colWidths=[3.5 * inch, 4.0 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("LEADING", (0, 0), (-1, -1), 13),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),  # keys
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0f172a")),  # values
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    20,
                ),  # add more gap to the right of keys
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
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

    title = f"Pediatric appendicitis Patient Report: {patient_title}"
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
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
        spaceAfter=3,
    )

    # Title block
    flow = []
    flow.append(Paragraph(title, title_style))
    flow.append(Spacer(1, 3))

    # Features
    feature_groups = {
        "Demographic Features": ["Age", "Sex", "Height", "Weight", "BMI"],
        "Scoring Features": ["Alvarado_Score", "Paedriatic_Appendicitis_Score"],
        "Clinical Features": [
            "Peritonitis",
            "Migratory_Pain",
            "Lower_Right_Abd_Pain",
            "Contralateral_Rebound_Tenderness",
            "Ipsilateral_Rebound_Tenderness",
            "Coughing_Pain",
            "Psoas_Sign",
            "Nausea",
            "Loss_of_Appetite",
            "Body_Temperature",
            "Dysuria",
            "Stool",
        ],
        "Laboratory Features": [
            "WBC_Count",
            "RBC_Count",
            "Hemoglobin",
            "RDW",
            "Thrombocyte_Count",
            "Neutrophil_Percentage",
            "Neutrophilia",
            "Segmented_Neutrophils",
            "CRP",
            "Ketones_in_Urine",
            "RBC_in_Urine",
            "WBC_in_Urine",
        ],
        "Ultrasound Features": [
            "US_Performed",
            "Appendix_on_US",
            "Appendix_Diameter",
            "Free_Fluids",
            "Appendix_Wall_Layers",
            "Target_Sign",
            "Perfusion",
            "Surrounding_Tissue_Reaction",
            "Pathological_Lymph_Nodes",
            "Bowel_Wall_Thickening",
            "Ileus",
            "Coprostasis",
            "Meteorism",
            "Enteritis",
            "Appendicolith",
            "Perforation",
            "Appendicular_Abscess",
            "Conglomerate_of_Bowel_Loops",
        ],
    }

    for section_title, feature_list in feature_groups.items():
        section_pairs = [
            (key, _fmt(getattr(patient, key, None)))  
            for key in feature_list
            if hasattr(patient, key)
        ]
        if not section_pairs:
            continue

        flow.append(_section_title(f"{section_title}"))
        flow.append(Spacer(1, 6))
        flow.append(_kv_table(section_pairs))
        flow.append(Spacer(1, 3))

    # Diagnosis
    flow.append(_section_title("Diagnosis"))
    flow.append(Spacer(1, 3))

    diag_color = (
        colors.HexColor("#16a34a")
        if patient.diagnosis == 0
        else colors.HexColor("#dc2626")
    )
    diag_style = ParagraphStyle(
        "Diag",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=diag_color,
        spaceAfter=3,
    )
    flow.append(
        Paragraph(f"Diagnosis: {patient.get_diagnosis_text().capitalize()}", diag_style)
    )
    flow.append(Spacer(1, 3))

    # --- Management Recommendation ---
    flow.append(_section_title("Management Recommendation"))
    flow.append(Spacer(1, 3))

    mgmt_color = ( colors.HexColor("#16a34a") if patient.management == "conservative" else colors.HexColor("#dc2626"))

    mgmt_style = ParagraphStyle(
        "Mgmt",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=mgmt_color,
        spaceAfter=3,
    )

    flow.append(
        Paragraph(f"Recommended management: {patient.get_management_text().capitalize()}",mgmt_style)
    )
    flow.append(Spacer(1, 3))

    # --- Predicted Length of Stay ---
    flow.append(_section_title("Predicted Length of Stay"))
    flow.append(Spacer(1, 3))

    los_style = ParagraphStyle(
        "LOS",
        parent=styles["BodyText"],
        fontSize=11,
        textColor=colors.HexColor("#0f172a"),
        leading=13,
    )

    los_text = patient.get_length_of_stay_text()

    flow.append(Paragraph(los_text, los_style))
    flow.append(Spacer(1, 3))

    doc.build(flow, onFirstPage=_header_footer, onLaterPages=_header_footer)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
