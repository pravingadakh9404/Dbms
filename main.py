import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

# YAHAN APNA NEON CONNECTION STRING PASTE KARNA
NEON_URL = "YOUR_NEON_URL_HERE"

class BookingReq(BaseModel):
    concert_id: int
    user_name: str
    email: str

def get_db():
    return psycopg2.connect(NEON_URL, cursor_factory=RealDictCursor)

@app.on_event("startup")
def setup_database():
    # App start hote hi Tables ban jayengi aur dummy data dal jayega
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS concerts (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            date_time TIMESTAMP,
            venue VARCHAR(100),
            price INTEGER
        );
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            concert_id INTEGER REFERENCES concerts(id),
            user_name VARCHAR(100),
            email VARCHAR(100)
        );
    ''')
    
    # Add dummy concerts if table is empty
    cur.execute("SELECT count(*) FROM concerts;")
    if cur.fetchone()['count'] == 0:
        cur.execute("INSERT INTO concerts (name, date_time, venue, price) VALUES ('Arijit Singh Live', '2026-05-10 18:00:00', 'Pune Arena', 1500)")
        cur.execute("INSERT INTO concerts (name, date_time, venue, price) VALUES ('Rock Fest 2026', '2026-05-15 19:00:00', 'Mumbai Stadium', 2000)")
    
    conn.commit()
    cur.close()
    conn.close()

@app.get("/")
def serve_home():
    # Yeh pehle wale path error ko fix karega
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(BASE_DIR, "index.html")
    return FileResponse(html_path)

@app.get("/api/concerts")
def get_concerts():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM concerts ORDER BY date_time;")
    concerts = cur.fetchall()
    cur.close()
    conn.close()
    return concerts

@app.post("/api/book")
def book_ticket(booking: BookingReq):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bookings (concert_id, user_name, email) VALUES (%s, %s, %s)",
            (booking.concert_id, booking.user_name, booking.email)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Ticket Booked Successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
