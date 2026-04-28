-- ============================================================
--  Musical Concert Ticket Booking System - SPPU DBMS Project
--  Paste this entire file into Supabase SQL Editor and Run
-- ============================================================

-- ─── TABLE: users ───────────────────────────────────────────
-- Stores customer/user details who book tickets
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100)        NOT NULL,
    email       VARCHAR(150)        NOT NULL UNIQUE,
    phone       VARCHAR(15)         NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ─── TABLE: concerts ────────────────────────────────────────
-- Stores concert/event details managed by admin
CREATE TABLE IF NOT EXISTS concerts (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(200)    NOT NULL,
    artist          VARCHAR(150)    NOT NULL,
    genre           VARCHAR(50)     NOT NULL,
    venue           VARCHAR(200)    NOT NULL,
    city            VARCHAR(100)    NOT NULL,
    concert_date    DATE            NOT NULL,
    concert_time    TIME            NOT NULL,
    total_seats     INTEGER         NOT NULL CHECK (total_seats > 0),
    available_seats INTEGER         NOT NULL CHECK (available_seats >= 0),
    ticket_price    NUMERIC(10, 2)  NOT NULL CHECK (ticket_price >= 0),
    image_url       TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure available seats never exceed total
    CONSTRAINT chk_seats CHECK (available_seats <= total_seats)
);

-- ─── TABLE: bookings ────────────────────────────────────────
-- Stores each ticket booking; links users ↔ concerts
CREATE TABLE IF NOT EXISTS bookings (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    concert_id      INTEGER         NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    num_tickets     INTEGER         NOT NULL DEFAULT 1 CHECK (num_tickets > 0),
    total_amount    NUMERIC(10, 2)  NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled')),
    booked_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ─── INDEXES for faster queries ──────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bookings_user_id    ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_concert_id ON bookings(concert_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status     ON bookings(status);

-- ─── SEED DATA: Sample Concerts ─────────────────────────────
INSERT INTO concerts (title, artist, genre, venue, city, concert_date, concert_time, total_seats, available_seats, ticket_price, image_url) VALUES
(
    'Echoes of the Night',
    'A.R. Rahman',
    'Fusion',
    'Jawaharlal Nehru Stadium',
    'Mumbai',
    '2025-09-15',
    '19:00:00',
    5000, 5000, 1200.00,
    'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=800'
),
(
    'Sufi Sutra Live',
    'Rahat Fateh Ali Khan',
    'Sufi',
    'Shaniwar Wada Grounds',
    'Pune',
    '2025-10-02',
    '18:30:00',
    3000, 3000, 800.00,
    'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800'
),
(
    'Rock the Valley',
    'Prateek Kuhad',
    'Indie Rock',
    'MMRDA Grounds',
    'Mumbai',
    '2025-10-20',
    '20:00:00',
    8000, 8000, 1500.00,
    'https://images.unsplash.com/photo-1501386761578-eaa54b8998e3?w=800'
),
(
    'Classical Monsoon Night',
    'Pandit Jasraj',
    'Classical',
    'Bal Gandharva Rang Mandir',
    'Pune',
    '2025-11-05',
    '17:00:00',
    1200, 1200, 600.00,
    'https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=800'
),
(
    'Bollywood Beats Fest',
    'Badshah & Neha Kakkar',
    'Bollywood',
    'DY Patil Stadium',
    'Navi Mumbai',
    '2025-11-25',
    '19:30:00',
    12000, 12000, 2000.00,
    'https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?w=800'
),
(
    'Jazz Under the Stars',
    'Louis Banks Quartet',
    'Jazz',
    'Nehru Centre Auditorium',
    'Mumbai',
    '2025-12-10',
    '20:30:00',
    800, 800, 1800.00,
    'https://images.unsplash.com/photo-1415201364774-f6f0bb35f28f?w=800'
);
