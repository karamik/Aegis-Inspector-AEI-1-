# Aegis-Inspector AEI-1 Docker image
# Autonomous drone inspection system

FROM python:3.10-slim

LABEL maintainer="International Group of Developers"
LABEL description="AEI-1: Autonomous Drone Inspector for Infrastructure Integrity"
LABEL version="1.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    libportaudio2 \
    sox \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY models/ ./models/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY *.sh ./

# Make scripts executable
RUN chmod +x *.sh

# Create directories for scan data
RUN mkdir -p /app/scan_data /app/missions

# Expose web planner port
EXPOSE 8080

# Default command (show help)
CMD ["make", "help"]
