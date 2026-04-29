CREATE TABLE concerts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    date_time TIMESTAMP NOT NULL,
    venue VARCHAR(100) NOT NULL,
    price INTEGER NOT NULL
);


CREATE TABLE bookings (
    id SERIAL PRIMARY KEY,
    concert_id INTEGER REFERENCES concerts(id) ON DELETE CASCADE,
    user_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL
);

INSERT INTO concerts (name, date_time, venue, price) 
VALUES 
('Arijit Singh Live', '2026-05-10 18:00:00', 'Pune Arena', 1500),
('Rock Fest 2026', '2026-05-15 19:00:00', 'Mumbai Stadium', 2000);



INSERT INTO bookings (concert_id, user_name, email) 
VALUES 
(1, 'Tejas Chavan', 'tejas.c@example.com');


SELECT * FROM concerts ORDER BY date_time ASC;

SELECT * FROM bookings WHERE user_name = 'Tejas Chavan';

SELECT bookings.user_name, bookings.email, concerts.name AS concert_name, concerts.venue
FROM bookings
INNER JOIN concerts ON bookings.concert_id = concerts.id;
