import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="testdb",
        user="postgres",
        password="Nplvicky@123",
        host="localhost",
        port="5432"
    )