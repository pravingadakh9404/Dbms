"""
Musical Concert Ticket Booking System
SPPU DBMS College Project – Backend (FastAPI + Supabase)
Author  : Your Name
Date    : 2025
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

# ─── Load environment variables from .env (local dev) ────────
load_dotenv()

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")

# ─── Supabase client ──────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title="Concert Ticket Booking API",
    description="SPPU DBMS Project – FastAPI + Supabase",
    version="1.0.0",
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
