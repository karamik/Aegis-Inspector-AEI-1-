# Aegis-Inspector AEI-1 Makefile
# Autonomous drone inspection system

.PHONY: help install calibrate plan scan analyze pilot clean

help:
	@echo "Aegis-Inspector AEI-1 Commands:"
	@echo "  make install      - Install dependencies and pull Docker image"
	@echo "  make calibrate    - Calibrate camera and acoustic sensor"
	@echo "  make plan         - Open web planner for mission path"
	@echo "  make scan         - Run autonomous scan (requires drone connected)"
	@echo "  make analyze      - Analyze scan data and generate report"
	@echo "  make pilot        - Run full pilot (calibrate + plan + scan + analyze)"
	@echo "  make clean        - Remove temporary files"

install:
	@echo "🛸 Installing Aegis-Inspector AEI-1..."
	docker pull ghcr.io/karamik/aei-1-pilot:latest
	pip3 install -r requirements.txt || true
	@echo "✅ Installation complete. Run 'make pilot' to start."

calibrate:
	@echo "🔧 Calibrating camera and acoustic sensor..."
	./calibrate.sh

plan:
	@echo "🗺️ Opening mission planner..."
	@echo "Visit http://localhost:8080 to draw inspection path"
	docker run --rm -p 8080:8080 ghcr.io/karamik/aei-1-pilot:latest planner

scan:
	@echo "🚁 Starting autonomous scan..."
	./scan.sh

analyze:
	@echo "📊 Analyzing scan data..."
	./analyze.sh

pilot:
	@echo "🚀 Starting Aegis-Inspector full pilot..."
	@echo "Step 1: Calibration"
	./calibrate.sh
	@echo "Step 2: Plan mission (open browser when ready)"
	read -p "Press Enter after planning mission..."
	@echo "Step 3: Autonomous scan"
	./scan.sh
	@echo "Step 4: Analysis"
	./analyze.sh
	@echo "✅ Pilot complete. Open report.html"

clean:
	@echo "🧹 Cleaning up..."
	rm -rf ./scan_data/*.jpg ./scan_data/*.wav
	rm -f report.html
	docker system prune -f
	@echo "✅ Clean complete."
