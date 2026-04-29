# routes.py
from fastapi import APIRouter, Query
from app.api.metrics_route import save_scenario
from app.schemas.scenario_comparision_schema import ApplyFilterRequest, ApplyFilterResponse, FilterResponse, SaveScenarioComparision
from app.services.Scenario_Comparision_service import apply_filters, get_filter_data


router = APIRouter()

@router.get("/filters", response_model=FilterResponse)
def fetch_filters(ta_name: str = Query(...)):
    return get_filter_data(ta_name)

# api/scenario_comparison_route.py


@router.post("/apply-filters", response_model=ApplyFilterResponse)
def apply_filter_api(payload: ApplyFilterRequest):
    return apply_filters(payload)

@router.post("/save", tags=["Scenario Selection"])
def save_scenario_api(payload: SaveScenarioComparision):
    return save_scenario(payload)