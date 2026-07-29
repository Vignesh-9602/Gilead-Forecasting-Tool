from typing import Dict, List, Optional
from pydantic import BaseModel

# =============================
# Persistency Schema 
# =============================
class PersistencyDefaultFilter(BaseModel):
    scenario_name: str
    indication: str
    lots: List[str]
    brand: str
    start_date: str
    end_date: str

class PersistencyFiltersResponse(BaseModel):
    ta_name: str
    scenario_names: List[str]
    data: Dict[str, Dict[str, Dict[str, List[str]]]]
    available_months: List[str] = []
    selected_filter: PersistencyDefaultFilter

class PersistencyApplyRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    lots: List[str]
    brand: str
    start_date: str
    end_date: str


class PersistencyApplyChild(BaseModel):
    label: str
    values: List[int]


class PersistencyApplyLotTable(BaseModel):
    lot: str
    children: List[PersistencyApplyChild]

class AvgVialsPerDoseLotTable(BaseModel):
    lot: str
    children: List[PersistencyApplyChild]

class DemandVialsLotTable(BaseModel):
    lot: str
    children: List[PersistencyApplyChild]

class InventoryTableChild(BaseModel):
    label: str
    values: List[float]


class InventoryTable(BaseModel):
    stock_percentage: float = 1
    children: List[InventoryTableChild]

class PersistencyApplyResponse(BaseModel):
    ta_name: str
    indication: str
    brand: str
    months: List[str]
    persistency_table: List[PersistencyApplyLotTable]
    avg_vials_per_dose_table: List[AvgVialsPerDoseLotTable]
    demand_vials_table: List[DemandVialsLotTable]
    inventory_table: InventoryTable


class PersistencyCalculateApplyRequest(BaseModel):
    ta_name: str
    curve_name: str

    start_month: int
    end_month: int

    start_value: float
    end_value: float

    method: str
    k_factor: float


class PersistencyCurveDetails(BaseModel):
    curve_name: str
    ta_name: str
    start_month: int
    end_month: int
    start_value: float
    end_value: float
    method: str
    k_factor: float



class PersistencyCurvePreview(BaseModel):
    months: List[str]
    values: List[float]


class PersistencyCurveListItem(BaseModel):
    curve_name: str
    method: str

class PersistencyCalculateApplyResponse(BaseModel):
    message: str
    curve_details: PersistencyCurveDetails
    curve_preview: PersistencyCurvePreview
    curve_list: List[PersistencyCurveListItem]

class PersistencyCurveListItemUpdate(BaseModel):
    curve_name: str

class PersistencyCurveNamesResponse(BaseModel):
    curve_list: List[PersistencyCurveListItemUpdate]


class PersistencyCurveDetails(BaseModel):
 
    curve_name: str
 
    ta_name: str
 
    start_month: Optional[str] = None
    end_month: Optional[str] = None
 
    start_value: Optional[float] = None
    end_value: Optional[float] = None
 
    # method: Optional[str] = None
 
    # k_factor: Optional[float] = None
 
 
class PersistencyCurvePreview(BaseModel):
    months: List[str]
    values: List[float]
 
 
class PersistencyCurveConfigResponse(BaseModel):
    curve_details: PersistencyCurveDetails
    curve_preview: PersistencyCurvePreview

class PersistencyCurveListItem(BaseModel):
    curve_name: str
    method: str

class PersistencyCurveListItemUpdate(BaseModel):
    curve_name: str

class DeletePersistencyCurveResponse(BaseModel):
    message: str
    curve_list: List[PersistencyCurveListItemUpdate]

class PersistencyCurvePeriod(BaseModel):
    curve_name: str
    start_date: str
    end_date: str


class PersistencyApplyCurveMapping(BaseModel):
    lot: str
    curves: List[PersistencyCurvePeriod]


class PersistencyApplyCurveRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    start_date: str
    end_date: str
    lots: List[str]
    lot_curve_mapping: List[PersistencyApplyCurveMapping]


class PersistencyApplyCurveChild(BaseModel):
    label: str
    values: List[int]


class PersistencyCurveMappingResponse(BaseModel):
    curve_name: str
    start_date: str
    end_date: str


class PersistencyApplyCurveLotTable(BaseModel):
    lot: str
    curve_mapping: List[PersistencyCurveMappingResponse] = []
    children: List[PersistencyApplyCurveChild]


class PersistencyApplyCurveResponse(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    persistency_table: List[PersistencyApplyCurveLotTable]
    avg_vials_per_dose_table: List[AvgVialsPerDoseLotTable]
    demand_vials_table: List[DemandVialsLotTable]
    inventory_table: InventoryTable

class AvgVialsEditRow(BaseModel):
    lot: str
    values: List[float]


class AvgVialsSaveRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    lots: List[str]
    avg_vials_per_dose_table: List[AvgVialsEditRow]

class AvgVialsSaveResponse(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    avg_vials_per_dose_table: List[AvgVialsPerDoseLotTable]
    demand_vials_table: List[DemandVialsLotTable]
    inventory_table: InventoryTable

class DemandEditChild(BaseModel):
    label: str
    values: List[float]


class DemandEditLot(BaseModel):
    lot: str
    children: List[DemandEditChild]


class DemandAdjustmentsSaveRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    demand_vials_table: List[DemandEditLot]


class TableChild(BaseModel):
    label: str
    values: List[float]


class LotTable(BaseModel):
    lot: str
    children: List[TableChild]


class InventoryTable(BaseModel):
    stock_percentage: float = 1
    children: List[TableChild]


class DemandAdjustmentsSaveResponse(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]

    demand_vials_table: List[LotTable]
    inventory_table: InventoryTable


class ComplianceConfiguration(BaseModel):
    lot: str
    compliance_percentage: float

class ConfigureComplianceGetResponse(BaseModel):
    ta_name: str
    indication: str
    brand: str
    compliance_configuration: List[ComplianceConfiguration]


class ConfigureComplianceApplyRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    compliance_configuration: List[ComplianceConfiguration]


class TableChild(BaseModel):
    label: str
    values: List[float]


class LotTable(BaseModel):
    lot: str
    children: List[TableChild]


class InventoryTable(BaseModel):
    stock_percentage: float = 1
    children: List[TableChild]


class ConfigureComplianceApplyResponse(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    demand_vials_table: List[LotTable]
    inventory_table: InventoryTable

class EditRowValuesConfiguration(BaseModel):
    selected_lots: List[str]
    start_month: str
    percentage_change_per_month: float
    number_of_months: int


class EditRowValuesRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    lots: List[str]
    edit_values_configuration: EditRowValuesConfiguration


class TableChild(BaseModel):
    label: str
    values: List[float]


class LotTable(BaseModel):
    lot: str
    children: List[TableChild]


class InventoryTable(BaseModel):
    stock_percentage: float = 1
    children: List[TableChild]


class EditRowValuesResponse(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    demand_vials_table: List[LotTable]
    inventory_table: InventoryTable

class InventoryStockUpdateRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    stock_percentage: float


class TableChild(BaseModel):
    label: str
    values: List[float]


class InventoryTable(BaseModel):
    stock_percentage: float
    children: List[TableChild]


class InventoryStockUpdateResponse(BaseModel):
    ta_name: str
    scenario_name: str
    indication: str
    brand: str
    months: List[str]
    inventory_table: InventoryTable
"""
Pydantic schemas for the Persistency Curve Upload API.
"""

from typing import List
from pydantic import BaseModel, Field


class CurveListItemUpdate(BaseModel):
    curve_name: str


class CurvePreviewUpdate(BaseModel):
    curve_name: str
    months: List[str]
    values: List[float]


class UploadCurveResponse(BaseModel):
    message: str
    curve_list: List[CurveListItemUpdate]
    curve_preview: CurvePreviewUpdate


class ErrorResponse(BaseModel):
    detail: str


class CurveValuesJSON(BaseModel):
    """
    Shape of the JSONB column `curve_values` stored in
    raw.persistency_curve_master.
    """
    months: List[str] = Field(..., description="Ordered month labels, e.g. M1, M2 ...")
    values: List[float] = Field(..., description="Persistency values aligned with `months`")