# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.Configuration_Route import router as Configuration_Router
from app.api.Model_Inputs_Route import router as Model_Inputs_Router
from app.api.Scenario_comparision_route import router as Scenario_comparision_router
from app.api.market_events_route import router as market_events_router
from app.api.Vial_Calculator_Route import router as Vial_Calculator_router
from app.api.Net_Revenue_Route import router as Net_Revenue_Router
from app.api.Output_Route import router as Output_Router
from app.api.monte_carlo_route import router as monte_carlo_router
from app.api.auth import router as login
from app.liver.api.liver_route import router as liver_router
app = FastAPI(title="TA Forecast API")

# Allow all CORS (frontend can be any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(Configuration_Router)
app.include_router(Model_Inputs_Router)
app.include_router(Scenario_comparision_router)
app.include_router(market_events_router)
app.include_router(Vial_Calculator_router)
app.include_router(Net_Revenue_Router)
app.include_router(Output_Router)
app.include_router(monte_carlo_router)
app.include_router(login)
app.include_router(liver_router)
