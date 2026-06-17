from fastapi import APIRouter
from app.schemas.Output_Schema import OutputApplyRequest, OutputFiltersResponse
from app.services.Output_service import get_output_apply_service, get_output_filters_service


router = APIRouter(prefix="/api/Output_screen", tags=["Output"])

@router.get( "/new-screen/filters/{ta_name}",response_model=OutputFiltersResponse)
def get_new_screen_filters(ta_name: str):
    return get_output_filters_service(ta_name)

@router.post("/demand-output/apply")
def apply_demand_output(payload: OutputApplyRequest):
    return get_output_apply_service(payload)