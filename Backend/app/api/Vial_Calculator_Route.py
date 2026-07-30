from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from app.schemas.Vial_Calculator_schema import AvgVialsSaveRequest, AvgVialsSaveResponse, ConfigureComplianceApplyRequest, ConfigureComplianceApplyResponse, ConfigureComplianceGetResponse, DeletePersistencyCurveResponse, DemandAdjustmentsSaveRequest, DemandAdjustmentsSaveResponse, EditRowValuesRequest, EditRowValuesResponse, InventoryStockUpdateRequest, InventoryStockUpdateResponse, PersistencyApplyCurveRequest, PersistencyApplyCurveResponse, PersistencyApplyRequest, PersistencyApplyResponse,PersistencyCalculateApplyRequest, PersistencyCalculateApplyResponse,PersistencyCurveConfigResponse, PersistencyCurveNamesResponse, PersistencyFiltersResponse, UpdateCurveRequest, UpdateCurveResponse, UploadCurveResponse
from app.services.Persistency_service import apply_persistency_curve_service, apply_persistency_service, calculate_apply_persistency_service, delete_persistency_curve_service, get_persistency_curve_config_service, get_persistency_curve_names_service, get_persistency_filters_service, save_avg_vials_per_dose_service
from app.services.Vial_Calculator_functions import apply_compliance_configuration_service, apply_edit_row_values_service, get_compliance_configuration_service, save_demand_adjustments_service, update_inventory_stock_service
from app.services.Upload_Curve import UploadFile,process_curve_upload, update_curve_service


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
    
@router.post("/avg-vials/save",response_model=AvgVialsSaveResponse)
def save_avg_vials_per_dose_api(
    payload: AvgVialsSaveRequest
):
    try:
        return save_avg_vials_per_dose_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while saving avg vials per dose: {str(e)}"
        )
    

@router.post( "/edit-complinace-row-values/apply",response_model=EditRowValuesResponse)
def apply_edit_row_values_api(
    payload: EditRowValuesRequest
):
    try:
        return apply_edit_row_values_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while applying edit row values: {str(e)}"
        )
    
@router.post( "/demand-adjustments/save", response_model=DemandAdjustmentsSaveResponse)
def save_demand_adjustments_api(
    payload: DemandAdjustmentsSaveRequest
):
    try:
        return save_demand_adjustments_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while saving demand adjustments: {str(e)}"
        )
    
@router.get("/compliance/configure",response_model=ConfigureComplianceGetResponse)
def get_compliance_configuration_api(
    ta_name: str,
    indication: str,
    brand: str,
    lots: Optional[List[str]] = Query(default=None, alias="lots[]")
):
    try:
        return get_compliance_configuration_service(
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching compliance configuration: {str(e)}"
        )


@router.post("/compliance/configure/apply",response_model=ConfigureComplianceApplyResponse)
def apply_compliance_configuration_api(
    payload: ConfigureComplianceApplyRequest
):
    try:
        return apply_compliance_configuration_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while applying compliance configuration: {str(e)}"
        )
    
@router.post("/inventory/stock-percentage/apply",response_model=InventoryStockUpdateResponse)
def update_inventory_stock_api(
    payload: InventoryStockUpdateRequest
):
    try:
        return update_inventory_stock_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while updating inventory stock percentage: {str(e)}"
        )
    
@router.post("/upload-curve", response_model=UploadCurveResponse)
async def upload_curve(
    file: UploadFile = File(..., description="Persistency curve Excel (.xlsx) file"),
    ta_name: str = Form(..., description="Therapeutic Area name"),
):
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported.")
 
    result = await process_curve_upload(file, ta_name)
    return result

@router.post("/Edit-curve", response_model=UpdateCurveResponse)
def update_curve(payload: UpdateCurveRequest):
    return update_curve_service(
        ta_name=payload.ta_name,
        curve_name=payload.curve_name,
        months=payload.months,
        values=payload.values,
    )