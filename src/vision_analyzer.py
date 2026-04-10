#!/usr/bin/env python3
"""
AEI-1 Vision Analyzer
Detects surface defects on any infrastructure (aircraft, drones, turbines, bridges)
Using computer vision and deep learning.
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple
import json
import os
import warnings
warnings.filterwarnings("ignore")

# -------------------- Configuration --------------------
class Config:
    IMG_SIZE = (224, 224)
    MODEL_PATH = "models/defect_detector.pt"
    CONFIDENCE_THRESHOLD = 0.6
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# -------------------- Neural Network Model --------------------
class DefectDetectorNet(nn.Module):
    """Multi‑class defect detector: crack, chip, oxidation, corrosion, delamination (surface)"""
    def __init__(self, num_classes=5):
        super(DefectDetectorNet, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1)
        )
        self.classifier = nn.Linear(256, num_classes)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)

# -------------------- Image Preprocessing --------------------
def load_image(image_path: str) -> Optional[np.ndarray]:
    if not os.path.exists(image_path):
        return None
    img = cv2.imread(image_path)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

def preprocess(img: np.ndarray) -> torch.Tensor:
    img_resized = cv2.resize(img, Config.IMG_SIZE)
    tensor = torch.from_numpy(img_resized).float().permute(2, 0, 1) / 255.0
    return tensor.unsqueeze(0)

# -------------------- Traditional CV (fallback) --------------------
def crack_density_sobel(img: np.ndarray) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    sobel = cv2.Sobel(gray, cv2.CV_64F, 1, 1, ksize=3)
    magnitude = np.sqrt(sobel**2)
    magnitude = magnitude / (magnitude.max() + 1e-8)
    return float(np.mean(magnitude > 0.3))

def chip_count_contours(img: np.ndarray) -> int:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return sum(1 for c in contours if cv2.contourArea(c) > 10)

def oxidation_ratio_hsv(img: np.ndarray) -> float:
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    # Typical healthy metallic/ceramic range; adjust per material
    lower = np.array([0, 0, 200])
    upper = np.array([180, 50, 255])
    mask = cv2.inRange(hsv, lower, upper)
    healthy_ratio = np.sum(mask > 0) / (img.shape[0] * img.shape[1])
    return float(1 - healthy_ratio)

# -------------------- Main Analyzer --------------------
class VisionAnalyzer:
    def __init__(self):
        self.device = Config.DEVICE
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(Config.MODEL_PATH):
            try:
                self.model = DefectDetectorNet(num_classes=5)
                self.model.load_state_dict(torch.load(Config.MODEL_PATH, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()
                print(f"Loaded model from {Config.MODEL_PATH}")
            except Exception as e:
                print(f"Warning: Could not load model: {e}. Using fallback.")
                self.model = None
        else:
            print("No model found. Using classical CV fallback.")

    def analyze_tile(self, image_path: str) -> Dict:
        img = load_image(image_path)
        if img is None:
            return {"defect_detected": False, "error": "Image not found"}

        # Classical features
        crack = crack_density_sobel(img)
        chips = chip_count_contours(img)
        oxidation = oxidation_ratio_hsv(img)

        defect_detected = (crack > 0.05) or (chips > 2) or (oxidation > 0.3)
        if crack > 0.05:
            defect_type = "crack"
        elif chips > 2:
            defect_type = "chip"
        elif oxidation > 0.3:
            defect_type = "oxidation"
        else:
            defect_type = "healthy"

        confidence = 0.9 if defect_detected else 0.8

        # Neural network if available
        if self.model:
            tensor = preprocess(img).to(self.device)
            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.softmax(logits, dim=1)
                conf, cls = torch.max(probs, 1)
                classes = ["crack", "chip", "oxidation", "corrosion", "healthy"]
                nn_type = classes[cls.item()]
                nn_conf = conf.item()
                # Combine: prefer NN if confident
                if nn_conf > Config.CONFIDENCE_THRESHOLD:
                    defect_detected = (nn_type != "healthy")
                    defect_type = nn_type
                    confidence = nn_conf

        return {
            "defect_detected": defect_detected,
            "defect_type": defect_type,
            "confidence": confidence,
            "metrics": {
                "crack_density": crack,
                "chip_count": chips,
                "oxidation_ratio": oxidation
            }
        }

    def analyze_batch(self, image_paths: List[str]) -> List[Dict]:
        results = []
        for idx, path in enumerate(image_paths):
            res = self.analyze_tile(path)
            res["tile_id"] = idx + 1
            res["image_path"] = path
            results.append(res)
        return results

if __name__ == "__main__":
    import sys
    analyzer = VisionAnalyzer()
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            print(json.dumps(analyzer.analyze_tile(f), indent=2))
    else:
        print("Usage: python vision_analyzer.py image1.jpg [image2.jpg ...]")
