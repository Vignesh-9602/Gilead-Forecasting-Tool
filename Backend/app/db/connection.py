import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Build absolute path to the .env file
env_path = Path(__file__).resolve().parent.parent / ".env"  # adjust based on actual location
load_dotenv(dotenv_path=env_path)

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )