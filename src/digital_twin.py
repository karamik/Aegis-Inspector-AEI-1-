#!/usr/bin/env python3
"""
AEI-1 Digital Twin
Tracks health of each inspected asset over time and predicts failures.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import numpy as np

class DigitalTwin:
    def __init__(self, db_path: str = "digital_twin_db.json"):
        self.db_path = db_path
        self.data: Dict[str, List[Dict]] = {}  # asset_id -> list of inspection records
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = {}

    def _save(self):
        with open(self.db_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_record(self, asset_id: str, inspection: Dict):
        """Store inspection results for an asset."""
        record = inspection.copy()
        if "timestamp" not in record:
            record["timestamp"] = datetime.now().isoformat()
        if asset_id not in self.data:
            self.data[asset_id] = []
        self.data[asset_id].append(record)
        self._save()

    def get_history(self, asset_id: str) -> List[Dict]:
        return self.data.get(asset_id, [])

    def compute_health_score(self, defect_ratio: float, severity: str = "low") -> float:
        """0=perfect, 1=critical"""
        base = defect_ratio
        if severity == "medium":
            base *= 1.5
        elif severity == "high":
            base *= 2.0
        return min(1.0, base)

    def predict_failure(self, asset_id: str) -> Dict:
        history = self.get_history(asset_id)
        if len(history) < 2:
            return {"risk": 0.0, "trend": "insufficient_data"}
        # Extract defect ratios over time
        ratios = [h.get("defect_ratio", 0) for h in history]
        x = np.arange(len(ratios))
        slope = np.polyfit(x, ratios, 1)[0]
        risk = min(1.0, max(0.0, ratios[-1] + slope))
        trend = "degrading" if slope > 0.02 else "stable" if abs(slope) <= 0.02 else "improving"
        return {"risk": float(risk), "trend": trend, "recommendation": "inspect soon" if risk > 0.3 else "ok"}

if __name__ == "__main__":
    twin = DigitalTwin()
    # example
    twin.add_record("test_wing", {"defect_ratio": 0.1, "defects": 2})
    print(twin.predict_failure("test_wing"))
