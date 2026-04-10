#!/usr/bin/env python3
"""
AEI-1 Acoustic Analyzer
Detects subsurface defects (delamination, loose bonds, hollow pockets)
via resonance analysis of tapping sounds.
"""

import numpy as np
import librosa
from scipy.spatial.distance import cosine
import os
import json
from typing import Dict, List, Optional, Tuple

# -------------------- Configuration --------------------
class Config:
    SAMPLE_RATE = 44100
    N_FFT = 2048
    HOP_LENGTH = 512
    MEL_BANDS = 128
    MFCC_COEFFS = 20
    DISTANCE_THRESHOLD = 0.35   # Cosine distance for flagging defect
    MIN_FREQ = 100
    MAX_FREQ = 5000

# -------------------- Feature Extraction --------------------
def load_audio(file_path: str) -> Tuple[Optional[np.ndarray], int]:
    if not os.path.exists(file_path):
        return None, 0
    try:
        y, sr = librosa.load(file_path, sr=Config.SAMPLE_RATE)
        return y, sr
    except:
        return None, 0

def extract_features(y: np.ndarray, sr: int) -> np.ndarray:
    """Extract aggregated feature vector for a tapping sound."""
    # Mel spectrogram -> MFCC
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=Config.MFCC_COEFFS,
                                n_fft=Config.N_FFT, hop_length=Config.HOP_LENGTH)
    # Spectral centroid (resonance peak)
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=Config.N_FFT,
                                             hop_length=Config.HOP_LENGTH)
    # Spectral bandwidth
    bw = librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=Config.N_FFT,
                                            hop_length=Config.HOP_LENGTH)
    # Zero-crossing rate (loose rattling)
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=Config.N_FFT,
                                             hop_length=Config.HOP_LENGTH)
    # Fundamental frequency (pitch)
    f0, _, _ = librosa.pyin(y, fmin=Config.MIN_FREQ, fmax=Config.MAX_FREQ,
                            sr=sr, hop_length=Config.HOP_LENGTH)
    f0 = np.nan_to_num(f0)

    # Aggregate: mean & std of MFCCs, centroid, bandwidth, ZCR, f0
    agg = []
    agg.extend(np.mean(mfcc, axis=1))
    agg.extend(np.std(mfcc, axis=1))
    agg.append(np.mean(cent))
    agg.append(np.std(cent))
    agg.append(np.mean(bw))
    agg.append(np.std(bw))
    agg.append(np.mean(zcr))
    agg.append(np.std(zcr))
    f0_vals = f0[f0 > 0]
    if len(f0_vals) > 0:
        agg.append(np.mean(f0_vals))
        agg.append(np.std(f0_vals))
    else:
        agg.extend([0, 0])
    return np.array(agg)

# -------------------- Baseline Manager --------------------
class AcousticAnalyzer:
    def __init__(self):
        self.baseline_features: Dict[int, np.ndarray] = {}

    def load_baseline(self, baseline_dir: str) -> bool:
        """Load baseline recordings (e.g., from healthy panel)"""
        if not os.path.isdir(baseline_dir):
            return False
        self.baseline_features = {}
        for fname in sorted(os.listdir(baseline_dir)):
            if fname.endswith(".wav"):
                # Expect naming: tile_001.wav, etc.
                parts = fname.replace(".wav", "").split("_")
                if len(parts) >= 2 and parts[0] == "tile":
                    tile_id = int(parts[1])
                    path = os.path.join(baseline_dir, fname)
                    y, sr = load_audio(path)
                    if y is not None:
                        self.baseline_features[tile_id] = extract_features(y, sr)
        return len(self.baseline_features) > 0

    def compare_tile(self, defect_audio_path: str, tile_id: int) -> Dict:
        if tile_id not in self.baseline_features:
            return {"defect_detected": False, "distance": 1.0, "error": "no baseline"}
        y, sr = load_audio(defect_audio_path)
        if y is None:
            return {"defect_detected": False, "distance": 1.0, "error": "audio load failed"}
        feat = extract_features(y, sr)
        baseline = self.baseline_features[tile_id]
        distance = cosine(baseline, feat)
        defect = distance > Config.DISTANCE_THRESHOLD
        confidence = min(1.0, distance / Config.DISTANCE_THRESHOLD) if defect else 1.0 - distance
        return {
            "defect_detected": defect,
            "distance": distance,
            "confidence": confidence,
            "tile_id": tile_id
        }

    def analyze_panel(self, defect_dir: str) -> List[Dict]:
        results = []
        for fname in sorted(os.listdir(defect_dir)):
            if fname.endswith(".wav"):
                parts = fname.replace(".wav", "").split("_")
                if len(parts) >= 2 and parts[0] == "tile":
                    tile_id = int(parts[1])
                    path = os.path.join(defect_dir, fname)
                    res = self.compare_tile(path, tile_id)
                    res["file"] = fname
                    results.append(res)
        return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python acoustic_analyzer.py <baseline_dir> <defect_dir>")
        sys.exit(1)
    analyzer = AcousticAnalyzer()
    if not analyzer.load_baseline(sys.argv[1]):
        print("Failed to load baseline")
        sys.exit(1)
    results = analyzer.analyze_panel(sys.argv[2])
    print(json.dumps(results, indent=2))
