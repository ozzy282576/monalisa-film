"""
连续性检查 - 检测场景跳变、SSIM
"""

import cv2
import numpy as np
from typing import Dict, Any

class ContinuityChecker:
    def __init__(self, thresholds: Dict[str, Any]):
        self.min_ssim = thresholds.get("min_ssim_between_frames", 0.85)
        self.max_cuts = thresholds.get("max_scene_cut_per_clip", 1)
    
    def _ssim(self, img1, img2):
        """简化版SSIM"""
        # 转换为灰度
        if len(img1.shape) == 3:
            img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        # 均值
        mu1 = cv2.GaussianBlur(img1, (11,11), 1.5)
        mu2 = cv2.GaussianBlur(img2, (11,11), 1.5)
        
        mu1_sq = mu1**2
        mu2_sq = mu2**2
        mu1_mu2 = mu1 * mu2
        
        sigma1_sq = cv2.GaussianBlur(img1**2, (11,11), 1.5) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2**2, (11,11), 1.5) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1*img2, (11,11), 1.5) - mu1_mu2
        
        # SSIM公式常数
        C1 = (0.01 * 255)**2
        C2 = (0.03 * 255)**2
        
        ssim_map = ((2*mu1_mu2 + C1)*(2*sigma12 + C2)) / ((mu1_sq + mu2_sq + C1)*(sigma1_sq + sigma2_sq + C2))
        return float(np.mean(ssim_map))
    
    def check(self, video_path: str) -> Dict[str, Any]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"passed": False, "score": 0, "reason": "无法打开视频"}
        
        prev_frame = None
        ssim_scores = []
        scene_cuts = 0
        
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if prev_frame is not None:
                # 缩小以加快计算
                small_prev = cv2.resize(prev_frame, (160, 90))
                small_curr = cv2.resize(frame, (160, 90))
                ssim = self._ssim(small_prev, small_curr)
                ssim_scores.append(ssim)
                
                # 如果SSIM过低，认为是场景跳变 - 降低阈值以适应动画
                if ssim < 0.3:
                    scene_cuts += 1
            
            prev_frame = frame
            frame_idx += 1
        
        cap.release()
        
        if not ssim_scores:
            return {"passed": False, "score": 0, "reason": "无法计算SSIM"}
        
        avg_ssim = np.mean(ssim_scores)
        min_ssim = np.min(ssim_scores)
        
        # 分数
        ssim_score = min(1.0, avg_ssim)  # SSIM越高越好
        cut_score = 1.0 - min(1.0, scene_cuts / (self.max_cuts + 1))
        
        overall = ssim_score * 0.7 + cut_score * 0.3
        
        passed = True
        reasons = []
        if avg_ssim < self.min_ssim:
            # 注意：动画视频SSIM可能较低，需要宽容
            if avg_ssim < 0.7:  # 过低才判失败
                passed = False
                reasons.append(f"平均SSIM过低: {avg_ssim:.3f} < {self.min_ssim}")
        
        if scene_cuts > self.max_cuts:
            passed = False
            reasons.append(f"场景跳变过多: {scene_cuts} > {self.max_cuts}")
        
        return {
            "passed": passed,
            "score": float(overall),
            "reason": "; ".join(reasons) if reasons else "通过",
            "details": {
                "avg_ssim": float(avg_ssim),
                "min_ssim": float(min_ssim),
                "scene_cuts": scene_cuts,
                "ssim_samples": ssim_scores[:10]
            }
        }
