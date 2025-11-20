from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# Allow Flutter app (web or mobile) to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to PostgreSQL
try:
    conn = psycopg2.connect(
        host="localhost",
        database="crisiscloud",
        user="myuser",
        password="mypassword",
        cursor_factory=RealDictCursor  # returns results as dictionaries
    )
    print("Database connection established!")
except Exception as e:
    print("Error connecting to database:", e)

@app.get("/locations")
def get_locations():
    """
    Returns a list of locations (latitude and longitude) from the database.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude FROM locations;")
        rows = cur.fetchall()
        cur.close()
        # Convert database rows to list of dictionaries
        return [{"lat": row["latitude"], "lng": row["longitude"]} for row in rows]
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def read_root():
    return {"message": "Welcome to the CrisisCloud API!"}

