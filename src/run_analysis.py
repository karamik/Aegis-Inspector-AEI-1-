#!/usr/bin/env python3
"""
AEI-1 Main Analysis Pipeline
Orchestrates vision, acoustic, SLAM, and digital twin to produce final inspection report.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision_analyzer import VisionAnalyzer
from src.acoustic_analyzer import AcousticAnalyzer
from src.digital_twin import DigitalTwin
from src.slam_navigation import SLAMNavigator


class AEIAnalyzer:
    def __init__(self, model_path: str = "models/defect_detector.pt"):
        self.vision = VisionAnalyzer()
        self.acoustic = AcousticAnalyzer()
        self.digital_twin = DigitalTwin()
        self.slam = SLAMNavigator()
        self.model_path = model_path

    def run(self, scan_dir: str, baseline_dir: Optional[str] = None) -> Dict:
        """
        Process all data in scan_dir (images + audio + navigation logs).
        If baseline_dir provided, use for acoustic comparison.
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "scan_dir": scan_dir,
            "total_tiles": 0,
            "defects_found": 0,
            "defect_list": [],
            "health_score": 1.0,
            "report_path": None
        }

        # 1. Load baseline for acoustic (if provided)
        if baseline_dir and os.path.isdir(baseline_dir):
            self.acoustic.load_baseline(baseline_dir)
            results["baseline_used"] = baseline_dir

        # 2. Find all image and audio files
        image_files = sorted([f for f in os.listdir(scan_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        audio_files = sorted([f for f in os.listdir(scan_dir) if f.endswith('.wav')])

        # Pair by tile_id (expect naming like tile_001.jpg and tile_001.wav)
        tile_data = {}
        for img in image_files:
            # Extract tile id from filename
            base = os.path.splitext(img)[0]
            if base.startswith("tile_"):
                tile_id = int(base.split("_")[1])
                tile_data[tile_id] = {"image": os.path.join(scan_dir, img), "audio": None}
        for aud in audio_files:
            base = os.path.splitext(aud)[0]
            if base.startswith("tile_"):
                tile_id = int(base.split("_")[1])
                if tile_id in tile_data:
                    tile_data[tile_id]["audio"] = os.path.join(scan_dir, aud)
                else:
                    tile_data[tile_id] = {"image": None, "audio": os.path.join(scan_dir, aud)}

        # 3. Analyze each tile
        for tile_id, paths in sorted(tile_data.items()):
            tile_result = {"tile_id": tile_id, "defect_detected": False, "defect_type": "healthy", "confidence": 0.0}
            # Vision
            if paths["image"] and os.path.exists(paths["image"]):
                vision_res = self.vision.analyze_tile(paths["image"])
                tile_result["vision"] = vision_res
                if vision_res.get("defect_detected"):
                    tile_result["defect_detected"] = True
                    tile_result["defect_type"] = vision_res.get("defect_type", "surface")
                    tile_result["confidence"] = vision_res.get("confidence", 0)
            # Acoustic
            if paths["audio"] and os.path.exists(paths["audio"]) and baseline_dir:
                acoustic_res = self.acoustic.compare_tile(paths["audio"], tile_id)
                tile_result["acoustic"] = acoustic_res
                if acoustic_res.get("defect_detected"):
                    tile_result["defect_detected"] = True
                    # If no visual defect but acoustic flags, it's subsurface
                    if tile_result["defect_type"] == "healthy":
                        tile_result["defect_type"] = "subsurface_delamination"
                    tile_result["confidence"] = max(tile_result["confidence"], acoustic_res.get("confidence", 0))
            # Store combined result
            tile_result["combined_health"] = 1.0 - (tile_result["confidence"] if tile_result["defect_detected"] else 0)
            results["defect_list"].append(tile_result)
            if tile_result["defect_detected"]:
                results["defects_found"] += 1

        results["total_tiles"] = len(tile_data)
        if results["total_tiles"] > 0:
            results["health_score"] = 1.0 - (results["defects_found"] / results["total_tiles"])
        else:
            results["health_score"] = 1.0

        # 4. Update digital twin (asset_id from scan_dir name)
        asset_id = os.path.basename(scan_dir)
        self.digital_twin.add_record(asset_id, {
            "defect_ratio": results["defects_found"] / max(1, results["total_tiles"]),
            "health_score": results["health_score"],
            "defects": results["defect_list"]
        })
        results["digital_twin"] = self.digital_twin.predict_failure(asset_id)

        return results

    def generate_html_report(self, results: Dict, output_path: str = "report.html"):
        """Generate simple HTML report from results."""
        html = f"""<!DOCTYPE html>
<html>
<head><title>AEI-1 Inspection Report</title>
<style>
body {{ font-family: monospace; background: #0a0a0a; color: #0f0; margin: 20px; }}
h1, h2 {{ color: #0f0; border-bottom: 1px solid #0f0; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #0f0; padding: 8px; text-align: left; }}
.defect {{ background: #3a1a1a; }}
.healthy {{ background: #1a3a1a; }}
</style>
</head>
<body>
<h1>AEI-1 Inspection Report</h1>
<p>Asset: {results['scan_dir']}</p>
<p>Time: {results['timestamp']}</p>
<h2>Summary</h2>
<ul>
<li>Total tiles: {results['total_tiles']}</li>
<li>Defects found: {results['defects_found']}</li>
<li>Health score: {results['health_score']:.2f}</li>
<li>Predicted risk: {results.get('digital_twin', {}).get('risk', 0):.2f}</li>
</ul>
<h2>Tile Details</h2>
<table>
<tr><th>Tile ID</th><th>Defect</th><th>Type</th><th>Confidence</th></tr>
"""
        for tile in results['defect_list']:
            cls = "defect" if tile['defect_detected'] else "healthy"
            html += f"<tr class='{cls}'><td>{tile['tile_id']}</td><td>{tile['defect_detected']}</td><td>{tile['defect_type']}</td><td>{tile['confidence']:.2f}</td></tr>"
        html += "</table></body></html>"
        with open(output_path, "w") as f:
            f.write(html)
        results["report_path"] = output_path

def main():
    parser = argparse.ArgumentParser(description="AEI-1 Main Analysis")
    parser.add_argument("--input", required=True, help="Directory with scan data (images + audio)")
    parser.add_argument("--baseline", help="Baseline recordings directory (for acoustic)")
    parser.add_argument("--output", default="report.html", help="Output HTML report")
    parser.add_argument("--model", default="models/defect_detector.pt", help="Path to vision model")
    args = parser.parse_args()

    analyzer = AEIAnalyzer(model_path=args.model)
    results = analyzer.run(args.input, baseline_dir=args.baseline)
    analyzer.generate_html_report(results, args.output)
    print(f"Analysis complete. Report saved to {args.output}")
    print(f"Defects found: {results['defects_found']} / {results['total_tiles']}")

if __name__ == "__main__":
    main()
