import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path
 
# Go up one level from db/ to reach app/ where .env lives
load_dotenv()
 
def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )
 