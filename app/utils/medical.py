from typing import Any, Literal


def calculate_neutrophilia(neutrophils_percentage: float) -> Literal["yes", "no"]:
    if neutrophils_percentage > 75:
        return "yes"
    return "no"


def calculate_alvarado_score(data: dict[str, Any]) -> int:
    """Source: https://www.mdcalc.com/calc/617/alvarado-score-acute-appendicitis"""
    alvarado_score = 0
    # Right lower quadrant tenderness
    if data["Lower_Right_Abd_Pain"] == "yes":
        alvarado_score += 2
    # Elevated temperature (37.3°C or 99.1°F)
    if data["Body_Temperature"] >= 37.3:
        alvarado_score += 1
    # Rebound tenderness
    if data["Ipsilateral_Rebound_Tenderness"] == "yes":
        alvarado_score += 1
    # Migration of pain to the right lower quadrant
    if data["Migratory_Pain"] == "yes":
        alvarado_score += 1
    # Anorexia
    if data["Loss_of_Appetite"] == "yes":
        alvarado_score += 1
    # Nausea or vomiting
    if data["Nausea"] == "yes":
        alvarado_score += 1
    # Leukocytosis >10,000
    if data["WBC_Count"] > 10:
        alvarado_score += 2
    # Leukocyte left shift: >75% neutrophils
    if data["Neutrophilia"] == "yes":
        alvarado_score += 1
    return alvarado_score


def calculate_pediatric_appendicits_score(data: dict[str, Any]) -> int:
    """Source: https://www.mdcalc.com/calc/3926/pediatric-appendicitis-score-pas"""
    pas = 0
    # RLQ tenderness to cough, percussion, or hopping
    if data["Coughing_Pain"] == "yes":
        pas += 2
    # Anorexia
    if data["Loss_of_Appetite"] == "yes":
        pas += 1
    # Fever: Temp ≥38.0ºC/100.4ºF
    if data["Body_Temperature"] >= 38:
        pas += 1
    # Nausea or vomiting
    if data["Nausea"] == "yes":
        pas += 1
    # Tenderness over right iliac fossa
    if data["Lower_Right_Abd_Pain"] == "yes":
        pas += 2
    # Leukocytosis: WBC >10,000
    if data["WBC_Count"] > 10:
        pas += 1
    # Neutrophilia: ANC >7,500
    if data["Neutrophilia"] == "yes":
        pas += 1
    # Migration of pain to RLQ
    if data["Migratory_Pain"] == "yes":
        pas += 1
    return pas
