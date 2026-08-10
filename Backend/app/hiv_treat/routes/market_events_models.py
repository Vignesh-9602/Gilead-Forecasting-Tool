from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field , model_validator , field_validator



class SelectedFilter(BaseModel):
    scenario_name: str
    markets: str
    products: str
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

    markets: str | None = None
    products: str | None = None

    @field_validator(
        "markets",
        "products",
        mode="before",
    )
    @classmethod
    def normalize_single_filter(cls, value):
        """
        Supports both formats:

            "Retail"
            ["Retail"]

        Converts empty values and "ALL" to None.
        """

        if value is None:
            return None

        if isinstance(value, (list, tuple, set)):
            cleaned_values = [
                str(item).strip()
                for item in value
                if item
                and str(item).strip().lower() != "all"
            ]

            if not cleaned_values:
                return None

            if len(cleaned_values) > 1:
                raise ValueError(
                    "Only one value can be selected."
                )

            return cleaned_values[0]

        normalized_value = str(value).strip()

        if (
            not normalized_value
            or normalized_value.lower() == "all"
        ):
            return None

        return normalized_value


class EditedTableRow(BaseModel):
    label: str
    editable: bool = True
    values: list[float] = Field(
        default_factory=list
    )
    children: list["EditedTableRow"] = Field(
        default_factory=list
    )


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
        "market_level",
        "product_market_level",
        "product_level",
        "market_product_level",
    ]

    edited_rows: list[str] = Field(
        default_factory=list
    )

    edited_table_rows: list[EditedTableRow] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_request(self):
        allowed_views = {
            "market_event": {
                "market_level",
                "product_market_level",
            },
            "product_event": {
                "product_level",
                "market_product_level",
            },
        }

        allowed = allowed_views[
            self.selected_tab
        ]

        if self.selected_table_view not in allowed:
            raise ValueError(
                f"{self.selected_table_view!r} is invalid for "
                f"{self.selected_tab!r}. "
                f"Allowed values: {sorted(allowed)}"
            )

        selected_market = (
            self.selected_filter.markets
        )

        selected_product = (
            self.selected_filter.products
        )

        # Product-Market view requires a selected product.
        if (
            self.selected_tab == "market_event"
            and self.selected_table_view
            == "product_market_level"
            and not selected_product
        ):
            raise ValueError(
                "products is required for "
                "product_market_level."
            )

        # Market-Product view requires a selected market.
        if (
            self.selected_tab == "product_event"
            and self.selected_table_view
            == "market_product_level"
            and not selected_market
        ):
            raise ValueError(
                "markets is required for "
                "market_product_level."
            )

        if not self.edited_table_rows:
            raise ValueError(
                "edited_table_rows cannot be empty."
            )

        return self


EditedTableRow.model_rebuild()

#delete


class DeleteEventRequest(BaseModel):
    ta_name: str = Field(..., min_length=1)
    scenario_name: str = Field(..., min_length=1)

    tab: Literal[
        "overall_event",
        "market_event",
        "product_event",
    ]

    event_name: str = Field(..., min_length=1)

#new product
class AddProductRequest(BaseModel):
    ta_name: str
    product_name: str

class UpdateProductRequest(BaseModel):
    ta_name: str
    product_name: str
    new_product_name: str

class DeleteProductRequest(BaseModel):
    ta_name: str
    product_name: str