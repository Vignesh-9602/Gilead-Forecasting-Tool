# app/api/auth_route.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.connection import get_connection

router = APIRouter(prefix="/api")

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login", tags=["Authentication"])
def login(payload: LoginRequest):

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT
                email,
                is_active
            FROM raw.app_users
            WHERE email = %s
              AND password = %s
            """,
            (
                payload.email,
                payload.password
            )
        )

        row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        email, is_active = row

        if not is_active:
            raise HTTPException(
                status_code=403,
                detail="User is inactive"
            )

        return {
            "success": True,
            "email": email
        }

    finally:
        cur.close()
        conn.close()