# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.route import router
from app.api.metrics_route import router as metrics_router

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
app.include_router(router)
app.include_router(metrics_router)