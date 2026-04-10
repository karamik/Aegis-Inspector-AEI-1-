#!/bin/bash
# Aegis-Inspector AEI-1 Calibration Script
# Calibrates camera, acoustic sensor, and drone positioning

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log "🔧 Aegis-Inspector Calibration"

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker not found. Please install Docker first."
fi

# Create calibration directory
mkdir -p ./calibration

# Step 1: Camera calibration (chessboard)
log "Step 1: Camera calibration"
if [ ! -f "./calibration/camera_matrix.npy" ]; then
    warn "No camera calibration found. Please place a chessboard pattern in front of the drone camera."
    warn "Press Enter when ready to capture calibration images..."
    read -r
    
    docker run --rm -it \
        -v $(pwd)/calibration:/app/calibration \
        --device /dev/video0:/dev/video0 \
        ghcr.io/karamik/aei-1-pilot:latest \
        python /app/src/calibrate_camera.py --device 0 --chessboard 9x6
else
    log "Camera calibration already exists."
fi

# Step 2: Acoustic baseline
log "Step 2: Acoustic sensor baseline"
if [ ! -f "./calibration/acoustic_baseline.npy" ]; then
    warn "Place the acoustic tapper against a known healthy surface."
    warn "Press Enter to record baseline resonance..."
    read -r
    
    docker run --rm -it \
        -v $(pwd)/calibration:/app/calibration \
        ghcr.io/karamik/aei-1-pilot:latest \
        python /app/src/calibrate_acoustic.py
else
    log "Acoustic baseline already exists."
fi

# Step 3: Drone connection test
log "Step 3: Drone connection test"
if command -v dji_sdk_demo &> /dev/null || command -v mavlink_router &> /dev/null; then
    log "Drone SDK detected. Testing connection..."
    docker run --rm \
        -v $(pwd)/calibration:/app/calibration \
        --network host \
        ghcr.io/karamik/aei-1-pilot:latest \
        python /app/src/test_drone_connection.py
else
    warn "No drone SDK found. Skipping drone connection test."
    warn "For autonomous flight, install PX4/ArduPilot or DJI SDK."
fi

log "✅ Calibration complete. Ready for mission planning."
