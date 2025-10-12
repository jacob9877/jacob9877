from typing import Literal

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

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
