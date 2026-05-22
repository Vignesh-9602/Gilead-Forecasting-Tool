from typing import Dict, List, Optional
from pydantic import BaseModel

# =============================
# Persistency Schema 
# =============================
class PersistencyFiltersResponse(BaseModel):
    ta_name: str
    data: Dict[str, Dict[str, List[str]]]


class PersistencyApplyRequest(BaseModel):
    ta_name: str
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


class PersistencyCurveNamesResponse(BaseModel):
    curve_list: List[PersistencyCurveListItem]


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


class PersistencyCurveConfigResponse(BaseModel):

    curve_details: PersistencyCurveDetails

    curve_preview: PersistencyCurvePreview

class PersistencyCurveListItem(BaseModel):
    curve_name: str
    method: str


class DeletePersistencyCurveResponse(BaseModel):
    message: str
    curve_list: List[PersistencyCurveListItem]

class PersistencyApplyCurveMapping(BaseModel):
    lot: str
    curve_name: str


class PersistencyApplyCurveRequest(BaseModel):
    ta_name: str
    indication: str
    brand: str
    start_date: str
    end_date: str
    lot_curve_mapping: List[PersistencyApplyCurveMapping]


class PersistencyApplyCurveChild(BaseModel):
    label: str
    values: List[int]


class PersistencyApplyCurveLotTable(BaseModel):
    lot: str
    curve_name: Optional[str] = None
    children: List[PersistencyApplyCurveChild]


class PersistencyApplyCurveResponse(BaseModel):
    ta_name: str
    indication: str
    brand: str
    months: List[str]
    persistency_table: List[PersistencyApplyCurveLotTable]
    avg_vials_per_dose_table: List[AvgVialsPerDoseLotTable]
    demand_vials_table: List[DemandVialsLotTable]
    inventory_table: InventoryTable