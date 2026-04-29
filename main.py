"""
Musical Concert Ticket Booking System
SPPU DBMS College Project – Backend (FastAPI + Direct PostgreSQL)
Author  : Your Name
Date    : 2025

Connection: Direct PostgreSQL via asyncpg (no supabase-py needed)
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import databases
import sqlalchemy

# ─── Load .env for local development ─────────────────────────
load_dotenv()

# ─── Database URL from environment variable ──────────────────
# On Render: set DATABASE_URL in Environment Variables
# Locally:   set it in your .env file
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

# ─── databases async client (uses asyncpg under the hood) ────
database = databases.Database(DATABASE_URL)

# ─── SQLAlchemy engine (only for metadata, not queries) ──────
engine = sqlalchemy.create_engine(DATABASE_URL)


# ══════════════════════════════════════════════════════════════
#  LIFESPAN – connect/disconnect DB on startup/shutdown
# ══════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    print("✅ Database connected successfully!")
    yield
    await database.disconnect()
    print("🔌 Database disconnected.")


# ─── FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title="Concert Ticket Booking API",
    description="SPPU DBMS Project – FastAPI + PostgreSQL (Direct Connection)",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins for development / college demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Serve the frontend HTML ──────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse("index.html")


# ══════════════════════════════════════════════════════════════
#  PYDANTIC MODELS  (request body schemas / validation)
# ══════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Schema for creating or looking up a user before booking."""
    name: str
    email: EmailStr
    phone: str


class BookingCreate(BaseModel):
    """Schema for creating a new booking."""
    user_id: int
    concert_id: int
    num_tickets: int = 1


# ══════════════════════════════════════════════════════════════
#  CONCERT ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/concerts", summary="List all available concerts")
async def get_concerts():
    """
    Returns all concerts that still have seats available,
    ordered by concert date (soonest first).
    """
    try:
        query = """
            SELECT *
            FROM concerts
            WHERE available_seats > 0
            ORDER BY concert_date ASC
        """
        rows = await database.fetch_all(query=query)
        return {"concerts": [dict(row) for row in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/concerts/{concert_id}", summary="Get a single concert by ID")
async def get_concert(concert_id: int):
    """Returns full details of one concert."""
    try:
        query = "SELECT * FROM concerts WHERE id = :id"
        row = await database.fetch_one(query=query, values={"id": concert_id})
        if not row:
            raise HTTPException(status_code=404, detail="Concert not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  USER ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/users", summary="Create or fetch a user by email")
async def create_or_get_user(user: UserCreate):
    """
    Checks if a user with the given email already exists.
    If yes  → returns existing user  (is_new: false)
    If no   → creates new user       (is_new: true)
    This avoids duplicate rows for repeat visitors.
    """
    try:
        # ── Check if user exists ──────────────────────────────
        existing = await database.fetch_one(
            query="SELECT * FROM users WHERE email = :email",
            values={"email": user.email},
        )
        if existing:
            return {"user": dict(existing), "is_new": False}

        # ── Insert new user ───────────────────────────────────
        new_user = await database.fetch_one(
            query="""
                INSERT INTO users (name, email, phone)
                VALUES (:name, :email, :phone)
                RETURNING *
            """,
            values={"name": user.name, "email": user.email, "phone": user.phone},
        )
        return {"user": dict(new_user), "is_new": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  BOOKING ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/bookings", summary="Book tickets for a concert")
async def create_booking(booking: BookingCreate):
    """
    Books tickets:
    1. Validates that the concert exists and has enough seats.
    2. Inserts a new booking record.
    3. Deducts seats from concerts.available_seats.
    """
    try:
        # ── Step 1: Fetch concert ─────────────────────────────
        concert = await database.fetch_one(
            query="SELECT id, title, available_seats, ticket_price FROM concerts WHERE id = :id",
            values={"id": booking.concert_id},
        )
        if not concert:
            raise HTTPException(status_code=404, detail="Concert not found")
        concert = dict(concert)

        # ── Step 2: Check seat availability ───────────────────
        if concert["available_seats"] < booking.num_tickets:
            raise HTTPException(
                status_code=400,
                detail=f"Only {concert['available_seats']} seats left!",
            )

        # ── Step 3: Calculate total amount ────────────────────
        total_amount = float(concert["ticket_price"]) * booking.num_tickets

        # ── Step 4: Insert booking ────────────────────────────
        new_booking = await database.fetch_one(
            query="""
                INSERT INTO bookings (user_id, concert_id, num_tickets, total_amount, status)
                VALUES (:user_id, :concert_id, :num_tickets, :total_amount, 'confirmed')
                RETURNING *
            """,
            values={
                "user_id":      booking.user_id,
                "concert_id":   booking.concert_id,
                "num_tickets":  booking.num_tickets,
                "total_amount": total_amount,
            },
        )

        # ── Step 5: Deduct seats ──────────────────────────────
        await database.execute(
            query="UPDATE concerts SET available_seats = available_seats - :num WHERE id = :id",
            values={"num": booking.num_tickets, "id": booking.concert_id},
        )

        return {
            "message":      "Booking confirmed! 🎶",
            "booking":      dict(new_booking),
            "total_amount": total_amount,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/bookings/user/{user_id}", summary="Get all bookings for a user")
async def get_user_bookings(user_id: int):
    """
    Returns all bookings for a user (confirmed + cancelled),
    with concert details joined via SQL JOIN — great for viva!
    """
    try:
        query = """
            SELECT
                b.id,
                b.user_id,
                b.concert_id,
                b.num_tickets,
                b.total_amount,
                b.status,
                b.booked_at,
                c.title        AS concert_title,
                c.artist       AS concert_artist,
                c.venue        AS concert_venue,
                c.city         AS concert_city,
                c.concert_date AS concert_date,
                c.concert_time AS concert_time,
                c.ticket_price AS concert_ticket_price
            FROM bookings b
            JOIN concerts c ON b.concert_id = c.id
            WHERE b.user_id = :user_id
            ORDER BY b.booked_at DESC
        """
        rows = await database.fetch_all(query=query, values={"user_id": user_id})

        # Reshape into nested format that frontend expects
        bookings = []
        for row in rows:
            r = dict(row)
            bookings.append({
                "id":           r["id"],
                "user_id":      r["user_id"],
                "concert_id":   r["concert_id"],
                "num_tickets":  r["num_tickets"],
                "total_amount": r["total_amount"],
                "status":       r["status"],
                "booked_at":    str(r["booked_at"]),
                "concerts": {
                    "title":        r["concert_title"],
                    "artist":       r["concert_artist"],
                    "venue":        r["concert_venue"],
                    "city":         r["concert_city"],
                    "concert_date": str(r["concert_date"]),
                    "concert_time": str(r["concert_time"]),
                    "ticket_price": r["concert_ticket_price"],
                },
            })

        return {"bookings": bookings}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/bookings/{booking_id}/cancel", summary="Cancel a booking")
async def cancel_booking(booking_id: int):
    """
    Cancels a booking:
    1. Validates booking exists and is not already cancelled.
    2. Sets status → 'cancelled'.
    3. Restores seats back to the concert.
    """
    try:
        # ── Step 1: Fetch booking ─────────────────────────────
        booking = await database.fetch_one(
            query="SELECT * FROM bookings WHERE id = :id",
            values={"id": booking_id},
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        booking = dict(booking)

        if booking["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="Booking is already cancelled")

        # ── Step 2: Update status ─────────────────────────────
        await database.execute(
            query="UPDATE bookings SET status = 'cancelled' WHERE id = :id",
            values={"id": booking_id},
        )

        # ── Step 3: Restore seats ─────────────────────────────
        await database.execute(
            query="UPDATE concerts SET available_seats = available_seats + :num WHERE id = :id",
            values={"num": booking["num_tickets"], "id": booking["concert_id"]},
        )

        return {"message": "Booking cancelled successfully.", "booking_id": booking_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))# Allow all origins for development / college demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Serve the frontend HTML ──────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse("index.html")


# ══════════════════════════════════════════════════════════════
#  PYDANTIC MODELS  (request body schemas)
# ══════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Schema for creating / looking-up a user before booking."""
    name: str
    email: EmailStr
    phone: str


class BookingCreate(BaseModel):
    """Schema for creating a new booking."""
    user_id: int
    concert_id: int
    num_tickets: int = 1


# ══════════════════════════════════════════════════════════════
#  CONCERT ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/concerts", summary="List all available concerts")
def get_concerts():
    """
    Returns all concerts that still have seats available,
    ordered by concert date (soonest first).
    """
    try:
        response = (
            supabase.table("concerts")
            .select("*")
            .gt("available_seats", 0)          # only concerts with seats
            .order("concert_date", desc=False)
            .execute()
        )
        return {"concerts": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/concerts/{concert_id}", summary="Get a single concert by ID")
def get_concert(concert_id: int):
    """Returns full details of one concert."""
    try:
        response = (
            supabase.table("concerts")
            .select("*")
            .eq("id", concert_id)
            .single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Concert not found")
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  USER ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/users", summary="Create or fetch a user by email")
def create_or_get_user(user: UserCreate):
    """
    Checks if a user with the given email already exists.
    If yes  → returns existing user.
    If no   → creates a new user and returns it.
    This avoids duplicate entries for repeat visitors.
    """
    try:
        # Check if user already exists
        existing = (
            supabase.table("users")
            .select("*")
            .eq("email", user.email)
            .execute()
        )
        if existing.data:
            return {"user": existing.data[0], "is_new": False}

        # Create new user
        new_user = (
            supabase.table("users")
            .insert({
                "name":  user.name,
                "email": user.email,
                "phone": user.phone,
            })
            .execute()
        )
        return {"user": new_user.data[0], "is_new": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  BOOKING ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/bookings", summary="Book tickets for a concert")
def create_booking(booking: BookingCreate):
    """
    Books tickets:
    1. Validates concert availability.
    2. Deducts seats from concert.available_seats.
    3. Inserts a new booking record.
    Uses simple check-then-update (sufficient for a college demo).
    """
    try:
        # ── Step 1: Fetch concert details ─────────────────────
        concert_resp = (
            supabase.table("concerts")
            .select("id, title, available_seats, ticket_price")
            .eq("id", booking.concert_id)
            .single()
            .execute()
        )
        concert = concert_resp.data
        if not concert:
            raise HTTPException(status_code=404, detail="Concert not found")

        # ── Step 2: Check seat availability ───────────────────
        if concert["available_seats"] < booking.num_tickets:
            raise HTTPException(
                status_code=400,
                detail=f"Only {concert['available_seats']} seats available."
            )

        # ── Step 3: Calculate total amount ────────────────────
        total_amount = float(concert["ticket_price"]) * booking.num_tickets

        # ── Step 4: Insert booking record ─────────────────────
        booking_resp = (
            supabase.table("bookings")
            .insert({
                "user_id":      booking.user_id,
                "concert_id":   booking.concert_id,
                "num_tickets":  booking.num_tickets,
                "total_amount": total_amount,
                "status":       "confirmed",
            })
            .execute()
        )

        # ── Step 5: Deduct seats ───────────────────────────────
        new_available = concert["available_seats"] - booking.num_tickets
        supabase.table("concerts").update(
            {"available_seats": new_available}
        ).eq("id", booking.concert_id).execute()

        return {
            "message": "Booking confirmed!",
            "booking": booking_resp.data[0],
            "total_amount": total_amount,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/bookings/user/{user_id}", summary="Get all bookings for a user")
def get_user_bookings(user_id: int):
    """
    Returns all bookings (confirmed + cancelled) for a given user.
    Joins concert details using Supabase's nested select.
    """
    try:
        response = (
            supabase.table("bookings")
            .select("*, concerts(title, artist, venue, city, concert_date, concert_time, ticket_price)")
            .eq("user_id", user_id)
            .order("booked_at", desc=True)
            .execute()
        )
        return {"bookings": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/bookings/{booking_id}/cancel", summary="Cancel a booking")
def cancel_booking(booking_id: int):
    """
    Cancels a booking:
    1. Sets booking status → 'cancelled'.
    2. Restores seats back to the concert.
    """
    try:
        # ── Step 1: Fetch the booking ─────────────────────────
        booking_resp = (
            supabase.table("bookings")
            .select("*")
            .eq("id", booking_id)
            .single()
            .execute()
        )
        booking = booking_resp.data
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="Booking already cancelled")

        # ── Step 2: Update booking status ─────────────────────
        supabase.table("bookings").update(
            {"status": "cancelled"}
        ).eq("id", booking_id).execute()

        # ── Step 3: Restore seats to concert ──────────────────
        concert_resp = (
            supabase.table("concerts")
            .select("available_seats")
            .eq("id", booking["concert_id"])
            .single()
            .execute()
        )
        current_seats = concert_resp.data["available_seats"]
        supabase.table("concerts").update(
            {"available_seats": current_seats + booking["num_tickets"]}
        ).eq("id", booking["concert_id"]).execute()

        return {"message": "Booking cancelled successfully.", "booking_id": booking_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))# Allow all origins for development / college demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Serve the frontend HTML ──────────────────────────────────
@app.get("/")
async def serve_frontend():
    # Yeh code dynamically exact folder ka path nikal lega
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(BASE_DIR, "index.html")
    
    return FileResponse(html_path)

# ══════════════════════════════════════════════════════════════
#  PYDANTIC MODELS  (request body schemas)
# ══════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Schema for creating / looking-up a user before booking."""
    name: str
    email: EmailStr
    phone: str


class BookingCreate(BaseModel):
    """Schema for creating a new booking."""
    user_id: int
    concert_id: int
    num_tickets: int = 1


# ══════════════════════════════════════════════════════════════
#  CONCERT ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/concerts", summary="List all available concerts")
def get_concerts():
    """
    Returns all concerts that still have seats available,
    ordered by concert date (soonest first).
    """
    try:
        response = (
            supabase.table("concerts")
            .select("*")
            .gt("available_seats", 0)          # only concerts with seats
            .order("concert_date", desc=False)
            .execute()
        )
        return {"concerts": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/concerts/{concert_id}", summary="Get a single concert by ID")
def get_concert(concert_id: int):
    """Returns full details of one concert."""
    try:
        response = (
            supabase.table("concerts")
            .select("*")
            .eq("id", concert_id)
            .single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Concert not found")
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  USER ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/users", summary="Create or fetch a user by email")
def create_or_get_user(user: UserCreate):
    """
    Checks if a user with the given email already exists.
    If yes  → returns existing user.
    If no   → creates a new user and returns it.
    This avoids duplicate entries for repeat visitors.
    """
    try:
        # Check if user already exists
        existing = (
            supabase.table("users")
            .select("*")
            .eq("email", user.email)
            .execute()
        )
        if existing.data:
            return {"user": existing.data[0], "is_new": False}

        # Create new user
        new_user = (
            supabase.table("users")
            .insert({
                "name":  user.name,
                "email": user.email,
                "phone": user.phone,
            })
            .execute()
        )
        return {"user": new_user.data[0], "is_new": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  BOOKING ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/bookings", summary="Book tickets for a concert")
def create_booking(booking: BookingCreate):
    """
    Books tickets:
    1. Validates concert availability.
    2. Deducts seats from concert.available_seats.
    3. Inserts a new booking record.
    Uses simple check-then-update (sufficient for a college demo).
    """
    try:
        # ── Step 1: Fetch concert details ─────────────────────
        concert_resp = (
            supabase.table("concerts")
            .select("id, title, available_seats, ticket_price")
            .eq("id", booking.concert_id)
            .single()
            .execute()
        )
        concert = concert_resp.data
        if not concert:
            raise HTTPException(status_code=404, detail="Concert not found")

        # ── Step 2: Check seat availability ───────────────────
        if concert["available_seats"] < booking.num_tickets:
            raise HTTPException(
                status_code=400,
                detail=f"Only {concert['available_seats']} seats available."
            )

        # ── Step 3: Calculate total amount ────────────────────
        total_amount = float(concert["ticket_price"]) * booking.num_tickets

        # ── Step 4: Insert booking record ─────────────────────
        booking_resp = (
            supabase.table("bookings")
            .insert({
                "user_id":      booking.user_id,
                "concert_id":   booking.concert_id,
                "num_tickets":  booking.num_tickets,
                "total_amount": total_amount,
                "status":       "confirmed",
            })
            .execute()
        )

        # ── Step 5: Deduct seats ───────────────────────────────
        new_available = concert["available_seats"] - booking.num_tickets
        supabase.table("concerts").update(
            {"available_seats": new_available}
        ).eq("id", booking.concert_id).execute()

        return {
            "message": "Booking confirmed!",
            "booking": booking_resp.data[0],
            "total_amount": total_amount,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/bookings/user/{user_id}", summary="Get all bookings for a user")
def get_user_bookings(user_id: int):
    """
    Returns all bookings (confirmed + cancelled) for a given user.
    Joins concert details using Supabase's nested select.
    """
    try:
        response = (
            supabase.table("bookings")
            .select("*, concerts(title, artist, venue, city, concert_date, concert_time, ticket_price)")
            .eq("user_id", user_id)
            .order("booked_at", desc=True)
            .execute()
        )
        return {"bookings": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/bookings/{booking_id}/cancel", summary="Cancel a booking")
def cancel_booking(booking_id: int):
    """
    Cancels a booking:
    1. Sets booking status → 'cancelled'.
    2. Restores seats back to the concert.
    """
    try:
        # ── Step 1: Fetch the booking ─────────────────────────
        booking_resp = (
            supabase.table("bookings")
            .select("*")
            .eq("id", booking_id)
            .single()
            .execute()
        )
        booking = booking_resp.data
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="Booking already cancelled")

        # ── Step 2: Update booking status ─────────────────────
        supabase.table("bookings").update(
            {"status": "cancelled"}
        ).eq("id", booking_id).execute()

        # ── Step 3: Restore seats to concert ──────────────────
        concert_resp = (
            supabase.table("concerts")
            .select("available_seats")
            .eq("id", booking["concert_id"])
            .single()
            .execute()
        )
        current_seats = concert_resp.data["available_seats"]
        supabase.table("concerts").update(
            {"available_seats": current_seats + booking["num_tickets"]}
        ).eq("id", booking["concert_id"]).execute()

        return {"message": "Booking cancelled successfully.", "booking_id": booking_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
