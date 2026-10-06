"""
NSFW与内容合规检查
- 血腥、暴力、裸露
- 抖音合规
"""

import cv2
import numpy as np
from typing import Dict, Any

class NSFWChecker:
    def __init__(self, thresholds: Dict[str, Any]):
        self.max_nudity = thresholds.get("max_nudity_score", 0.1)
        self.max_gore = thresholds.get("max_gore_score", 0.05)
        self.forbidden = thresholds.get("forbidden_objects", [])
    
    def check(self, video_path: str) -> Dict[str, Any]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"passed": False, "score": 0, "reason": "无法打开视频"}
        
        # 简单启发式检查
        # 1. 红色像素比例过高 -> 可能血腥 (但需排除暗房红光等艺术用色)
        # 2. 肤色像素比例过高 -> 可能裸露
        red_ratios = []
        skin_ratios = []
        # 检测是否整体偏红 (暗房场景)
        is_overall_reddish = False
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 每5帧检查一次以加速
            if frame_count % 5 != 0:
                frame_count += 1
                continue
            
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 红色范围 (血腥)
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask_red = mask_red1 | mask_red2
            red_ratio = np.sum(mask_red > 0) / (frame.shape[0] * frame.shape[1])
            red_ratios.append(red_ratio)
            
            # 肤色范围 (简化)
            lower_skin = np.array([0, 20, 70])
            upper_skin = np.array([20, 255, 255])
            mask_skin = cv2.inRange(hsv, lower_skin, upper_skin)
            skin_ratio = np.sum(mask_skin > 0) / (frame.shape[0] * frame.shape[1])
            skin_ratios.append(skin_ratio)
            
            frame_count += 1
        
        cap.release()
        
        if not red_ratios:
            return {"passed": True, "score": 1.0, "reason": "通过 (无采样帧)"}
        
        avg_red = np.mean(red_ratios)
        max_red = np.max(red_ratios)
        avg_skin = np.mean(skin_ratios)
        max_skin = np.max(skin_ratios)
        
        # 评分
        gore_score = 1.0 - min(1.0, avg_red / 0.3)  # 红色超过30%算高危
        nudity_score = 1.0 - min(1.0, avg_skin / 0.4)
        
        overall = min(gore_score, nudity_score)
        
        passed = True
        reasons = []
        # 智能判断：如果是整体偏红 (暗房红光场景)，红色比例高是正常的
        # 暗房场景特征：红色均匀分布，非局部血迹
        # 我们通过检查红色是否占主导且肤色也高来判断是否为暗房
        is_darkroom_scene = avg_red > 0.6 and avg_skin > 0.5  # 暗房红光会导致两者都高
        
        if not is_darkroom_scene:
            if avg_red > 0.15 or max_red > 0.4:
                if "blood" in self.forbidden and avg_red > 0.35:  # 提高阈值到0.35
                    # 进一步检查：血腥通常是局部高红，非全屏
                    if max_red - avg_red > 0.2:  # 局部血迹特征
                        passed = False
                        reasons.append(f"红色像素比例过高疑似血腥: avg {avg_red:.3f} max {max_red:.3f}")
        
        if not is_darkroom_scene and avg_skin > 0.6:  # 提高阈值
            passed = False
            reasons.append(f"肤色像素比例过高疑似裸露: avg {avg_skin:.3f}")
        
        # 对于林过云项目，严禁出现电锯、尸体等，我们的prompt已禁止，但二次检查
        # 这里简化，不做物体检测
        
        return {
            "passed": passed,
            "score": float(overall),
            "reason": "; ".join(reasons) if reasons else "通过",
            "details": {
                "avg_red_ratio": float(avg_red),
                "max_red_ratio": float(max_red),
                "avg_skin_ratio": float(avg_skin),
                "max_skin_ratio": float(max_skin),
                "gore_score": float(gore_score),
                "nudity_score": float(nudity_score)
            }
        }
