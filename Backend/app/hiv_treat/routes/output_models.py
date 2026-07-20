from pydantic import BaseModel, Field , model_validator

class OutputScreenResponse(BaseModel):
    ta_name: str
    available_scenarios: list[str]
    markets: list[str]
    products: list[str]
    available_months: list[str]
    selected_filter: dict