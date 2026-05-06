# routes.py
from fastapi import APIRouter, Query
from app.api.metrics_route import save_scenario
from app.schemas.scenario_comparision_schema import ApplyFilterRequest, ApplyFilterResponse, FilterResponse, FinalizeScenarioRequest, FinalizeScenarioResponse, SaveScenarioComparision, SaveScenarioResponse
from app.services.Scenario_Comparision_service import apply_filters, get_filter_data
from app.services.Secenario_Selection import finalize_scenarios


router = APIRouter(prefix="/api")

@router.get("/scenario/filters/{ta_name}", response_model=FilterResponse,tags=["Scenario_Comparision"])
def fetch_filters(ta_name: str):
    return get_filter_data(ta_name)



@router.post("/scenario/apply-filters", response_model=ApplyFilterResponse,tags=["Scenario_Comparision"])
def apply_filter_api(payload: ApplyFilterRequest):
    return apply_filters(payload)

@router.post("/scenario/save", response_model=SaveScenarioResponse,tags=["Scenario_Comparision"])
def save_scenario_api(payload: SaveScenarioComparision):
    return save_scenario(payload)

@router.post("/scenario/finalize-scenarios", response_model=FinalizeScenarioResponse,tags=["Scenario_Comparision"])
def finalize_scenarios_api(payload: FinalizeScenarioRequest):
    return finalize_scenarios(payload)