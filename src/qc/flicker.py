"""
闪烁检查 - 检测亮度闪烁、颜色跳变
"""

import cv2
import numpy as np
from typing import Dict, Any

class FlickerChecker:
    def __init__(self, thresholds: Dict[str, Any]):
        self.max_brightness_variance = thresholds.get("max_brightness_variance", 30)
        self.max_flicker_freq = thresholds.get("max_flicker_frequency", 0.1)
    
    def check(self, video_path: str) -> Dict[str, Any]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"passed": False, "score": 0, "reason": "无法打开视频"}
        
        brightness = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # 计算亮度 (V通道)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            v = np.mean(hsv[:,:,2])
            brightness.append(v)
        
        cap.release()
        
        if len(brightness) < 10:
            return {"passed": False, "score": 0, "reason": "帧数不足"}
        
        brightness = np.array(brightness)
        variance = np.var(brightness)
        mean_brightness = np.mean(brightness)
        
        # 检测高频闪烁：相邻帧亮度差
        diffs = np.abs(np.diff(brightness))
        flicker_count = np.sum(diffs > 20)  # 亮度跳变超过20算闪烁
        flicker_ratio = flicker_count / len(diffs)
        
        # 分数
        var_score = 1.0 - min(1.0, variance / (self.max_brightness_variance * 2))
        flicker_score = 1.0 - min(1.0, flicker_ratio / self.max_flicker_freq)
        
        overall = (var_score * 0.5 + flicker_score * 0.5)
        
        passed = True
        reasons = []
        # 亮度方差高可能是渐变 (如暗房显影)，需结合闪烁频率判断
        # 只有高方差 + 高闪烁频率才算真正闪烁
        if variance > self.max_brightness_variance and flicker_ratio > 0.05:
            # 如果是渐变，diffs会很小，variance虽高但flicker_ratio低，不应判失败
            if flicker_ratio > self.max_flicker_freq:
                passed = False
                reasons.append(f"亮度方差过高: {variance:.1f} > {self.max_brightness_variance} 且闪烁频繁")
        if flicker_ratio > self.max_flicker_freq:
            passed = False
            reasons.append(f"闪烁频率过高: {flicker_ratio:.3f} > {self.max_flicker_freq}")
        
        return {
            "passed": passed,
            "score": float(overall),
            "reason": "; ".join(reasons) if reasons else "通过",
            "details": {
                "brightness_variance": float(variance),
                "mean_brightness": float(mean_brightness),
                "flicker_ratio": float(flicker_ratio),
                "brightness_samples": brightness[:10].tolist()
            }
        }
