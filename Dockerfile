# ─────────────────────────────────────────────────────────────
#  Dockerfile – Concert Ticket Booking System
#  Optimized for Render.com free-tier deployment
# ─────────────────────────────────────────────────────────────

# Use slim Python image to keep the container size small
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy only requirements first (Docker layer caching – faster rebuilds)
COPY requirements.txt .

# Install Python dependencies (no cache to save space)
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into the container
COPY . .

# Expose the port FastAPI will run on
EXPOSE 8000

# Start the app with uvicorn
# --host 0.0.0.0  → accessible from outside the container
# --port 8000     → Render maps this automatically
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
