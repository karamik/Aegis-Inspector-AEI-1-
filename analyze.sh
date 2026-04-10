#!/bin/bash
# Aegis-Inspector AEI-1 Analysis Script
# Processes scan data and generates defect report

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

# Find latest scan directory
if [ -z "$1" ]; then
    SCAN_DIR=$(ls -td ./scan_data/*/ 2>/dev/null | head -1)
    if [ -z "$SCAN_DIR" ]; then
        error "No scan data found. Run 'make scan' first or specify directory."
    fi
else
    SCAN_DIR="$1"
fi

log "📊 Analyzing scan data from $SCAN_DIR"

# Check if data exists
if [ ! -d "$SCAN_DIR" ]; then
    error "Scan directory not found: $SCAN_DIR"
fi

# Run analysis container
docker run --rm \
    -v "$(pwd)/models:/app/models" \
    -v "$(pwd)/config:/app/config" \
    -v "$SCAN_DIR:/app/scan_data" \
    -v "$(pwd):/app/output" \
    ghcr.io/karamik/aei-1-pilot:latest \
    python /app/src/run_analysis.py \
        --input /app/scan_data \
        --output /app/output/report.html \
        --model /app/models/defect_detector.pt

if [ $? -eq 0 ]; then
    log "✅ Analysis complete. Report saved to report.html"
    
    # Try to open report in browser
    if command -v xdg-open &> /dev/null; then
        xdg-open report.html
    elif command -v open &> /dev/null; then
        open report.html
    elif command -v start &> /dev/null; then
        start report.html
    else
        log "Please open report.html manually"
    fi
    
    # Display summary
    echo ""
    echo "========================================="
    echo "  AEGIS-INSPECTOR AEI-1 SCAN REPORT"
    echo "========================================="
    if [ -f "./report_summary.txt" ]; then
        cat ./report_summary.txt
    fi
else
    error "Analysis failed"
fi
