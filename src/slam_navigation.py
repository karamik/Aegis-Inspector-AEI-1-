#!/usr/bin/env python3
"""
AEI-1 SLAM Navigation Module
Provides localization and mapping for autonomous drone inspection.
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
import json

class SLAMNavigator:
    """
    Simplified visual‑inertial SLAM for drone positioning relative to asset.
    Uses ORB features and optical flow for real‑time pose estimation.
    """
    def __init__(self):
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.prev_frame = None
        self.prev_keypoints = None
        self.prev_descriptors = None
        self.camera_matrix = None
        self.dist_coeffs = None

    def load_calibration(self, calib_file: str):
        """Load camera intrinsic parameters."""
        with open(calib_file, 'r') as f:
            data = json.load(f)
        self.camera_matrix = np.array(data["camera_matrix"])
        self.dist_coeffs = np.array(data["dist_coeffs"])

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process new frame, estimate motion relative to previous frame.
        Returns translation and rotation estimates.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp, des = self.orb.detectAndCompute(gray, None)

        result = {"dx": 0.0, "dy": 0.0, "dz": 0.0, "yaw": 0.0, "pitch": 0.0, "roll": 0.0}

        if self.prev_keypoints is not None and self.prev_descriptors is not None and des is not None:
            matches = self.bf.match(self.prev_descriptors, des)
            matches = sorted(matches, key=lambda x: x.distance)[:50]
            if len(matches) > 10:
                src_pts = np.float32([self.prev_keypoints[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
                E, mask = cv2.findEssentialMat(src_pts, dst_pts, self.camera_matrix, method=cv2.RANSAC, prob=0.999, threshold=1.0)
                if E is not None:
                    _, R, t, _ = cv2.recoverPose(E, src_pts, dst_pts, self.camera_matrix)
                    result["dx"] = t[0, 0]
                    result["dy"] = t[1, 0]
                    result["dz"] = t[2, 0]
                    # Convert rotation matrix to Euler angles (simplified)
                    sy = np.sqrt(R[0,0]**2 + R[1,0]**2)
                    result["yaw"] = np.arctan2(R[1,0], R[0,0])
                    result["pitch"] = np.arctan2(-R[2,0], sy)
                    result["roll"] = np.arctan2(R[2,1], R[2,2])

        self.prev_frame = gray
        self.prev_keypoints = kp
        self.prev_descriptors = des
        return result

class MissionPlanner:
    """
    Generate inspection path over 3D surface model.
    """
    @staticmethod
    def generate_grid(bbox: Tuple[float, float, float, float, float, float],
                      step_m: float = 0.1) -> List[Tuple[float, float, float]]:
        """
        Generate 3D grid waypoints within bounding box (xmin, xmax, ymin, ymax, zmin, zmax).
        """
        xmin, xmax, ymin, ymax, zmin, zmax = bbox
        xs = np.arange(xmin, xmax + step_m, step_m)
        ys = np.arange(ymin, ymax + step_m, step_m)
        zs = np.arange(zmin, zmax + step_m, step_m)
        waypoints = [(float(x), float(y), float(z)) for x in xs for y in ys for z in zs]
        return waypoints

    @staticmethod
    def generate_spiral(center: Tuple[float, float, float],
                        radius_m: float, turns: int = 3) -> List[Tuple[float, float, float]]:
        """
        Generate spiral path for scanning cylindrical or rounded surfaces.
        """
        cx, cy, cz = center
        waypoints = []
        for t in np.linspace(0, turns * 2 * np.pi, 100):
            r = radius_m * (t / (turns * 2 * np.pi))
            x = cx + r * np.cos(t)
            y = cy + r * np.sin(t)
            z = cz + t * 0.1
            waypoints.append((x, y, z))
        return waypoints

if __name__ == "__main__":
    planner = MissionPlanner()
    # Example: grid on a 2m x 1m surface at z=0
    waypoints = planner.generate_grid((0, 2, 0, 1, 0, 0), step_m=0.2)
    print(f"Generated {len(waypoints)} waypoints")
    with open("waypoints.json", "w") as f:
        json.dump(waypoints, f)
