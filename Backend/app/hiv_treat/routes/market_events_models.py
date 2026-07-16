from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field , model_validator



class SelectedFilter(BaseModel):
    scenario_name: str
    markets: List[str]
    products: List[str]
    start_date: str
    end_date: str


class ApplyFiltersRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter


#edit

class EditSelectedFilter(BaseModel):
    scenario_name: str
    start_date: str
    end_date: str
    markets: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)


class EditedTableRow(BaseModel):
    label: str
    editable: bool = True
    values: list[float] = Field(default_factory=list)
    children: list["EditedTableRow"] = Field(default_factory=list)


class EditSaveRequest(BaseModel):
    ta_name: str
    selected_filter: EditSelectedFilter

    selected_tab: Literal[
        "market_event",
        "product_event",
    ]

    selected_metric: Literal[
        "market_share",
        "market_volume",
    ]

    selected_table_view: Literal[
        "product_level",
        "product_market_level",
        "market_level",
        "market_product_level",
    ]

    edited_headers: list[str]
    edited_rows: list[str] = Field(default_factory=list)
    edited_table_rows: list[EditedTableRow]

    @model_validator(mode="after")
    def validate_request(self):
        allowed_views = {
            "market_event": {
                "product_level",
                "product_market_level",
            },
            "product_event": {
                "market_level",
                "market_product_level",
            },
        }

        if self.selected_table_view not in allowed_views[self.selected_tab]:
            raise ValueError(
                f"{self.selected_table_view!r} is invalid for "
                f"{self.selected_tab!r}"
            )

        if not self.edited_headers:
            raise ValueError("edited_headers cannot be empty")

        if len(self.edited_headers) != len(set(self.edited_headers)):
            raise ValueError("edited_headers contains duplicates")

        return self


EditedTableRow.model_rebuild()