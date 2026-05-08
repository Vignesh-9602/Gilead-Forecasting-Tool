# routes.py
from fastapi import APIRouter, Query
from app.schemas.scenario_comparision_schema import ApplyFilterRequest, ApplyFilterResponse, ClearScenarioRequest, ClearScenarioResponse, FilterResponse, FinalizeScenarioRequest, FinalizeScenarioResponse, SaveScenarioComparision, SaveScenarioResponse, ScenarioStatusRequest, ScenarioStatusResponse
from app.services.Scenario_Comparision_service import apply_filters, get_filter_data
from app.services.Secenario_Selection import clear_scenario_selections, finalize_scenarios, get_scenario_status, save_scenario_comparision


router = APIRouter(prefix="/api")

@router.get("/scenario/filters/{ta_name}", response_model=FilterResponse,tags=["Scenario_Comparision"])
def fetch_filters(ta_name: str):
    return get_filter_data(ta_name)



@router.post("/scenario/apply-filters", response_model=ApplyFilterResponse,tags=["Scenario_Comparision"])
def apply_filter_api(payload: ApplyFilterRequest):
    return apply_filters(payload)

@router.post("/scenario/save", response_model=SaveScenarioResponse,tags=["Scenario_Comparision"])
def save_scenario_api(payload: SaveScenarioComparision):
    return save_scenario_comparision(payload)

@router.post("/scenario/finalize-scenarios",response_model=FinalizeScenarioResponse,tags=["Scenario_Comparision"])
def finalize_scenarios_api(payload: FinalizeScenarioRequest):
    return finalize_scenarios(payload)

@router.post("/scenario/status",response_model=ScenarioStatusResponse,tags=["Scenario_Comparision"])
def get_scenario_status_api(payload: ScenarioStatusRequest):
    return get_scenario_status(payload)

@router.post(
    "/scenario/clear",response_model=ClearScenarioResponse,tags=["Scenario_Comparision"])
def clear_scenario_api(payload: ClearScenarioRequest):
    return clear_scenario_selections(payload)