from fastapi import APIRouter, HTTPException
from app.schemas.Vial_Calculator_schema import DeletePersistencyCurveResponse, PersistencyApplyCurveRequest, PersistencyApplyCurveResponse, PersistencyApplyRequest, PersistencyApplyResponse,PersistencyCalculateApplyRequest, PersistencyCalculateApplyResponse,PersistencyCurveConfigResponse, PersistencyCurveNamesResponse, PersistencyFiltersResponse
from app.services.Persistency_service import apply_persistency_curve_service, apply_persistency_service, calculate_apply_persistency_service, delete_persistency_curve_service, get_persistency_curve_config_service, get_persistency_curve_names_service, get_persistency_filters_service



router = APIRouter(prefix="/api/persistency", tags=["Vial_Calculator"])


@router.get("/filters/{ta_name}", response_model=PersistencyFiltersResponse)
def get_persistency_filters(ta_name: str):
    try:
        return get_persistency_filters_service(ta_name)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching persistency filters: {str(e)}"
        )
    
@router.post( "/apply", response_model=PersistencyApplyResponse)
def apply_persistency(payload: PersistencyApplyRequest):
    try:
        return apply_persistency_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while applying persistency: {str(e)}"
        )
    
@router.post("/calculate-apply",response_model=PersistencyCalculateApplyResponse)
def calculate_apply_persistency(
    payload: PersistencyCalculateApplyRequest
):
    try:

        return calculate_apply_persistency_service(
            payload
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error while calculating persistency curve: {str(e)}"
        )

@router.get("/curves/{ta_name}", response_model=PersistencyCurveNamesResponse)
def get_persistency_curve_names(ta_name: str):
    try:
        return get_persistency_curve_names_service(ta_name)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching persistency curves: {str(e)}"
        )
    
@router.get("/curve-details/{curve_name}",response_model=PersistencyCurveConfigResponse
)
def get_persistency_curve_config(
    curve_name: str
):
    try:
        return get_persistency_curve_config_service(
            curve_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching persistency curve config: {str(e)}"
        )
    
@router.delete("/delete-curve/{curve_name}",response_model=DeletePersistencyCurveResponse
)
def delete_persistency_curve(
    curve_name: str
):
    try:

        return delete_persistency_curve_service(
            curve_name
        )
    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error while deleting persistency curve: {str(e)}"
        )
    

@router.post( "/apply-curve",response_model=PersistencyApplyCurveResponse)
def apply_persistency_curve(
    payload: PersistencyApplyCurveRequest
):
    try:
        return apply_persistency_curve_service(
            payload
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while applying persistency curve: {str(e)}"
        )