import re
from typing import Literal

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.utils.db import get_db_cursor_cm

OverallStatusOptions = Literal[
    "ACTIVE_NOT_RECRUITING",
    "COMPLETED",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
    "RECRUITING",
    "SUSPENDED",
    "TERMINATED",
    "WITHDRAWN",
    "AVAILABLE",
    "NO_LONGER_AVAILABLE",
    "TEMPORARILY_NOT_AVAILABLE",
    "APPROVED_FOR_MARKETING",
    "WITHHELD",
    "UNKNOWN",
]


class GetClinicalTrialsInput(BaseModel):
    condition: str = Field(
        ...,
        description="Name of the condition the clinical trial is for",
        example="lung cancer",
    )
    overall_status: list[OverallStatusOptions] | None = Field(
        default=None,
        description="Status of clinical trials to filter by, e.g. if the trial is recruiting then it will be status 'RECRUITING'. This is not a required field and actually shouldn't be provided unless you actually need to filter by a different clinical trial status.",
        example=["NOT_YET_RECRUITING", "RECRUITING"],
    )


@tool(
    description="Get current data about clinical trials using clinicaltrials.gov API. Returns a list of summaries about clinical trials satisfying the filter criteria sorted in descending order by LastUpdatePostDate.",
    args_schema=GetClinicalTrialsInput,
)
def get_clinical_trials(
    condition: str,
    overall_status: list[OverallStatusOptions] | None = None,
) -> list[dict]:
    # Default overall_status
    if overall_status is None:
        overall_status = ["NOT_YET_RECRUITING", "RECRUITING"]

    fields = [
        "NCTId",
        "BriefTitle",
        "Acronym",
        "OverallStatus",
        "Condition",
        "PrimaryOutcomeMeasure",
        "PrimaryOutcomeTimeFrame",
        "LeadSponsorName",
        "CollaboratorName",
        "Sex",
        "MinimumAge",
        "MaximumAge",
        "StudyType",
        "LastUpdatePostDate",
    ]
    query_params = {
        "query.cond": condition,
        "query.locn": "florida",
        "filter.overallStatus": "|".join(overall_status),
        "fields": "|".join(fields),
        "sort": "LastUpdatePostDate",  # Sort by most recent LastUpdatePostDate
    }

    response = requests.get(
        "https://clinicaltrials.gov/api/v2/studies", params=query_params, timeout=30
    )  # Must use requests library because API returns 403 when using httpx

    response.raise_for_status()

    response_body = response.json()
    studies = response_body["studies"]
    return studies


class GetClinicalTrialByNCTIdInput(BaseModel):
    nct_id: str = Field(
        pattern=r"^[Nn][Cc][Tt]0*[1-9]\d{0,7}$",
        description="NCT Number of a study. Basically the ID of a clinical trial.",
    )


@tool(
    description="Get complete information about a clinical trial by its NCT Number/Id. This tool should be used if more information about the clinical trial is required beyond what is provided in the summary.",
    args_schema=GetClinicalTrialByNCTIdInput,
)
def get_clinical_trial_by_id(nct_id: str) -> dict:
    response = requests.get(
        f"https://clinicaltrials.gov/api/v2/studies/{nct_id}",
        allow_redirects=True,
        timeout=30,  # Allow redirects because the API may return 301 redirect to the study info
    )  # Must use requests library because API returns 403 when using httpx
    response.raise_for_status()

    response_body = response.json()
    return response_body


class GetPatientsForAttributesInput(BaseModel):
    name: str | None = Field(
        default=None,
        description="Patient nickname",
        example="John D",
    )

    first_name: str | None = Field(
        default=None, description="Patient's first name", example="John"
    )

    last_name: str | None = Field(
        default=None, description="Patient's first name", example="Doe"
    )

    email: str | None = Field(default=None, description="johndoe@example.com")


get_patients_for_attributes_description = (
    "Get a subset of information about patients that satisfy the attributes. "
    "Use to retrieve patient IDs a clinician is looking for. All attributes are optional. "
    "If none are provided however, raises an error."
)


def get_patients_for_attributes(
    clinician_user_id: int,
    patients_table: Literal[
        "breast_cancer_patients", "pediatric_appendicitis_patients"
    ],
    name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> list[dict]:
    def to_boolean_prefix_query(s: str) -> str:
        """
        Build a BOOLEAN MODE query that matches if *any* token is present (OR semantics),
        with prefix matching on each token (token*).
        """
        if not s:
            return ""
        terms = re.findall(r"[0-9A-Za-z\u00C0-\u017F'-]+", s)
        terms = [t for t in terms if t]
        if not terms:
            return ""

        tokens = [f"{t}*" for t in terms]
        # Space-separated => OR semantics in BOOLEAN MODE
        return " ".join(tokens)

    # Fall back: combine first/last if name not provided (still useful for p.name)
    if not name:
        parts: list[str] = []
        if first_name:
            parts.append(first_name)
        if last_name:
            parts.append(last_name)
        name = " ".join(parts) if parts else None

    if not first_name:
        if name:
            first_name = name
        elif last_name:
            first_name = last_name

    if not last_name:
        if name:
            last_name = name
        elif first_name:
            last_name = first_name

    ors: list[str] = []
    params: list = [clinician_user_id]

    # Precompute FULLTEXT queries
    q_name = to_boolean_prefix_query(name) if name else ""
    q_first_name = to_boolean_prefix_query(first_name) if first_name else ""
    q_last_name = to_boolean_prefix_query(last_name) if last_name else ""

    operation = f"""
        SELECT
            p.id,
            p.name,
            p.pending_email,
            CASE
                WHEN p.user_id IS NULL THEN NULL
                ELSE CAST(JSON_OBJECT(
                    'first_name', u.first_name,
                    'last_name',  u.last_name,
                    'email',      u.email
                ) AS JSON)
            END AS patient_user_info
        FROM {patients_table} AS p
        LEFT JOIN users AS u
            ON u.id = p.user_id
        WHERE p.clinician_user_id = %s
    """

    # Email strict equality
    if email:
        ors.append("(p.user_id IS NOT NULL AND u.email = %s)")
        params.append(email)
        ors.append("(p.pending_email IS NOT NULL AND p.pending_email = %s)")
        params.append(email)

    # FT on patients' name
    if q_name:
        ors.append("MATCH(p.name) AGAINST (%s IN BOOLEAN MODE)")
        params.append(q_name)

    # FULLTEXT on users' FIRST NAME only
    if q_first_name:
        ors.append(
            "(p.user_id IS NOT NULL AND "
            " MATCH(u.first_name) AGAINST (%s IN BOOLEAN MODE))"
        )
        params.append(q_first_name)

    # FULLTEXT on users' LAST NAME only
    if q_last_name:
        ors.append(
            "(p.user_id IS NOT NULL AND "
            " MATCH(u.last_name) AGAINST (%s IN BOOLEAN MODE))"
        )
        params.append(q_last_name)

    if not ors:
        raise ValueError(
            "At least one of name, first_name, last_name, or email is required."
        )

    operation += " AND (" + " OR ".join(ors) + ")"

    # Relevance ordering: sum scores from whichever FT parts are present; then stable by id
    score_clauses: list[str] = []
    score_params: list[str] = []
    if q_name:
        score_clauses.append("COALESCE(MATCH(p.name) AGAINST (%s IN BOOLEAN MODE), 0)")
        score_params.append(q_name)
    if q_first_name:
        score_clauses.append(
            "COALESCE(MATCH(u.first_name) AGAINST (%s IN BOOLEAN MODE), 0)"
        )
        score_params.append(q_first_name)
    if q_last_name:
        score_clauses.append(
            "COALESCE(MATCH(u.last_name) AGAINST (%s IN BOOLEAN MODE), 0)"
        )
        score_params.append(q_last_name)

    if score_clauses:
        operation += " ORDER BY (" + " + ".join(score_clauses) + ") DESC, p.id"
        params.extend(score_params)
    else:
        operation += " ORDER BY p.id"

    with get_db_cursor_cm() as cursor:
        cursor.execute(operation, tuple(params))
        rows = cursor.fetchall()

    return rows
