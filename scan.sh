#!/bin/bash
# Aegis-Inspector AEI-1 Autonomous Scan Script
# Executes inspection mission on pre-planned path

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

# Check if mission file exists
MISSION_FILE="./missions/current_mission.json"
if [ ! -f "$MISSION_FILE" ]; then
    error "No mission file found. Run 'make plan' first to create a mission."
fi

log "🚁 Starting autonomous inspection scan"

# Create scan data directory
SCAN_DIR="./scan_data/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SCAN_DIR"

# Step 1: Connect to drone and upload mission
log "Uploading mission to drone..."
docker run --rm \
    -v $(pwd)/missions:/app/missions \
    -v $(pwd)/scan_data:/app/scan_data \
    --network host \
    ghcr.io/karamik/aei-1-pilot:latest \
    python /app/src/upload_mission.py --mission "$MISSION_FILE" --output "$SCAN_DIR"

# Step 2: Execute autonomous flight (if drone armed)
log "Executing autonomous scan (drone will fly pre-programmed path)"
log "Monitor via web dashboard at http://localhost:8080"
docker run --rm \
    -v $(pwd)/scan_data:/app/scan_data \
    --network host \
    -p 8080:8080 \
    ghcr.io/karamik/aei-1-pilot:latest \
    python /app/src/execute_scan.py --output "$SCAN_DIR"

# Step 3: Download scan data (images + acoustic recordings)
log "Downloading scan data from drone..."
docker run --rm \
    -v $(pwd)/scan_data:/app/scan_data \
    --network host \
    ghcr.io/karamik/aei-1-pilot:latest \
    python /app/src/download_scan.py --output "$SCAN_DIR"

# Step 4: Verify data integrity
log "Verifying scan data integrity..."
NUM_IMAGES=$(find "$SCAN_DIR" -name "*.jpg" | wc -l)
NUM_AUDIO=$(find "$SCAN_DIR" -name "*.wav" | wc -l)

log "Captured $NUM_IMAGES images and $NUM_AUDIO audio samples"

if [ "$NUM_IMAGES" -eq 0 ]; then
    error "No images captured. Scan failed."
fi

# Save scan metadata
cat > "$SCAN_DIR/metadata.json" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "mission_file": "$MISSION_FILE",
    "num_images": $NUM_IMAGES,
    "num_audio": $NUM_AUDIO,
    "status": "completed"
}
EOF

log "✅ Scan completed. Data saved to $SCAN_DIR"
log "Run 'make analyze' to process the scan data."
