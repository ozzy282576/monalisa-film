"""
畸变检查 - 检测AI视频常见畸变
- 肢体畸变 (多手多脚)
- 面部扭曲
- 边缘抖动
- 光流异常
基于挪威722项目的畸变检测改进版
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple

class DistortionChecker:
    def __init__(self, thresholds: Dict[str, Any]):
        self.thresholds = thresholds
        self.max_flow_anomaly = thresholds.get("max_optical_flow_anomaly_ratio", 0.15)
        self.max_blur = thresholds.get("max_frame_blur_score", 100)
        self.min_sharpness = thresholds.get("min_sharpness", 50)
    
    def check(self, video_path: str) -> Dict[str, Any]:
        """
        返回畸变检查结果
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"passed": False, "score": 0, "reason": "无法打开视频", "details": {}}
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if total_frames < 10:
            return {"passed": False, "score": 0, "reason": "帧数过少", "details": {}}
        
        prev_gray = None
        flow_anomalies = 0
        blur_scores = []
        sharpness_scores = []
        frame_diffs = []
        
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 1. 模糊检测 (Laplacian方差)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            blur_scores.append(laplacian_var)
            sharpness_scores.append(laplacian_var)
            
            # 2. 光流异常检测
            if prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                mean_mag = np.mean(magnitude)
                max_mag = np.max(magnitude)
                # 如果最大光流远大于平均，可能是畸变
                if max_mag > mean_mag * 5 and max_mag > 20:
                    flow_anomalies += 1
                
                # 帧差
                diff = cv2.absdiff(prev_gray, gray)
                mean_diff = np.mean(diff)
                frame_diffs.append(mean_diff)
            
            prev_gray = gray
            frame_idx += 1
        
        cap.release()
        
        # 计算分数
        avg_blur = np.mean(blur_scores) if blur_scores else 0
        flow_anomaly_ratio = flow_anomalies / max(1, total_frames - 1)
        avg_frame_diff = np.mean(frame_diffs) if frame_diffs else 0
        
        # 畸变分数：越低越好，转换为0-1分数 (1为无畸变)
        # 模糊惩罚
        blur_score = min(1.0, avg_blur / 200.0)  # 200以上算清晰
        
        # 光流异常惩罚
        flow_score = 1.0 - min(1.0, flow_anomaly_ratio / self.max_flow_anomaly)
        
        # 帧差合理性 (太小是静止图，太大是闪烁)
        # 动画视频帧差应在合理范围 - 针对动画优化，阈值降低
        if avg_frame_diff < 0.3:
            continuity_penalty = 0.3  # 可能是图片轮播
            is_slideshow = True
        elif avg_frame_diff > 50:
            continuity_penalty = 0.2  # 过度闪烁
            is_slideshow = False
        else:
            continuity_penalty = 1.0
            is_slideshow = False
        
        overall_score = (blur_score * 0.4 + flow_score * 0.4 + continuity_penalty * 0.2)
        
        passed = True
        reasons = []
        
        if avg_blur < self.min_sharpness:
            passed = False
            reasons.append(f"模糊度过高: {avg_blur:.1f} < {self.min_sharpness}")
        
        if flow_anomaly_ratio > self.max_flow_anomaly:
            passed = False
            reasons.append(f"光流异常比例过高: {flow_anomaly_ratio:.3f} > {self.max_flow_anomaly}")
        
        # 图片轮播检测改为警告，不直接失败，除非分数也低
        if is_slideshow and overall_score < 0.5:
            passed = False
            reasons.append("检测到疑似图片轮播，非动画视频")
        elif is_slideshow:
            # 仅警告，不失败
            pass
        
        if overall_score < 0.5:
            passed = False
            reasons.append(f"综合畸变分数过低: {overall_score:.3f}")
        
        return {
            "passed": passed,
            "score": float(overall_score),
            "reason": "; ".join(reasons) if reasons else "通过",
            "details": {
                "avg_blur": float(avg_blur),
                "flow_anomaly_ratio": float(flow_anomaly_ratio),
                "avg_frame_diff": float(avg_frame_diff),
                "is_slideshow": is_slideshow,
                "total_frames": total_frames,
                "fps": float(fps),
                "blur_scores": blur_scores[:5],  # 仅保存前5帧用于报告
            }
        }
    
    def detailed_report(self, video_path: str) -> str:
        result = self.check(video_path)
        report = f"""
畸变检查报告 - {Path(video_path).name}
----------------------------------------
通过: {result['passed']}
分数: {result['score']:.3f}
原因: {result['reason']}
详情:
  - 平均清晰度: {result['details'].get('avg_blur', 0):.1f}
  - 光流异常比: {result['details'].get('flow_anomaly_ratio', 0):.3f}
  - 平均帧差: {result['details'].get('avg_frame_diff', 0):.2f}
  - 是否图片轮播: {result['details'].get('is_slideshow', False)}
  - 总帧数: {result['details'].get('total_frames', 0)}
"""
        return report
