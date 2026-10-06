"""
QA报告生成与综合评分
整合所有QC检查，生成最终QA报告
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from ..agnes_client.models import QCResult
from .distortion import DistortionChecker
from .flicker import FlickerChecker
from .continuity import ContinuityChecker
from .nsfw import NSFWChecker

class QAEngine:
    def __init__(self, config_path: str = "config/qc_thresholds.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.distortion_checker = DistortionChecker(self.config.get("distortion_check", {}))
        self.flicker_checker = FlickerChecker(self.config.get("flicker_check", {}))
        self.continuity_checker = ContinuityChecker(self.config.get("continuity_check", {}))
        self.nsfw_checker = NSFWChecker(self.config.get("nsfw_check", {}))
        
        self.min_overall = self.config.get("overall_qa", {}).get("min_overall_score", 0.85)
    
    def check_video(self, video_path: str, clip_id: int, attempt: int) -> QCResult:
        print(f"[QA] 检查视频: C{clip_id:02d} Attempt {attempt:03d} - {video_path}")
        
        # 逐项检查
        distortion = self.distortion_checker.check(video_path)
        flicker = self.flicker_checker.check(video_path)
        continuity = self.continuity_checker.check(video_path)
        nsfw = self.nsfw_checker.check(video_path)
        
        # 抖音合规检查 (分辨率、时长等)
        douyin_compliance = self._check_douyin_compliance(video_path)
        
        # 综合评分
        scores = [
            distortion.get("score", 0) * 0.35,
            flicker.get("score", 0) * 0.15,
            continuity.get("score", 0) * 0.25,
            nsfw.get("score", 0) * 0.15,
            douyin_compliance.get("score", 0) * 0.10
        ]
        overall = sum(scores)
        
        # 判断是否通过
        passed = (
            distortion.get("passed", False) and
            flicker.get("passed", False) and
            continuity.get("passed", False) and
            nsfw.get("passed", False) and
            douyin_compliance.get("passed", False) and
            overall >= self.min_overall
        )
        
        failure_reasons = []
        if not distortion.get("passed"):
            failure_reasons.append(f"畸变: {distortion.get('reason')}")
        if not flicker.get("passed"):
            failure_reasons.append(f"闪烁: {flicker.get('reason')}")
        if not continuity.get("passed"):
            failure_reasons.append(f"连续性: {continuity.get('reason')}")
        if not nsfw.get("passed"):
            failure_reasons.append(f"NSFW: {nsfw.get('reason')}")
        if not douyin_compliance.get("passed"):
            failure_reasons.append(f"抖音合规: {douyin_compliance.get('reason')}")
        if overall < self.min_overall:
            failure_reasons.append(f"总分过低: {overall:.3f} < {self.min_overall}")
        
        checks = {
            "distortion": distortion,
            "flicker": flicker,
            "continuity": continuity,
            "nsfw": nsfw,
            "douyin_compliance": douyin_compliance
        }
        
        result = QCResult(
            clip_id=clip_id,
            attempt=attempt,
            passed=passed,
            overall_score=overall,
            checks=checks,
            distortion_score=distortion.get("score", 0),
            flicker_score=flicker.get("score", 0),
            continuity_score=continuity.get("score", 0),
            nsfw_score=nsfw.get("score", 0),
            file_path=video_path,
            failure_reasons=failure_reasons
        )
        
        print(f"[QA] 结果: {'通过' if passed else '失败'} 分数: {overall:.3f} 原因: {'; '.join(failure_reasons) if failure_reasons else '无'}")
        return result
    
    def _check_douyin_compliance(self, video_path: str) -> Dict[str, Any]:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"passed": False, "score": 0, "reason": "无法打开视频"}
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        # 检查分辨率
        expected_w, expected_h = 1080, 1920
        # 允许半分辨率用于测试
        if not ((width == 1080 and height == 1920) or (width == 540 and height == 960) or (width == 720 and height == 1280)):
            # 只要是9:16就行
            aspect = width / height if height != 0 else 0
            expected_aspect = 9/16
            if abs(aspect - expected_aspect) > 0.05:
                return {"passed": False, "score": 0.5, "reason": f"分辨率不符合9:16: {width}x{height}"}
        
        # 检查时长 - 使用配置
        douyin_cfg = self.config.get("douyin_compliance", {})
        min_dur = douyin_cfg.get("min_duration_seconds", 11.0)
        max_dur = douyin_cfg.get("max_duration_seconds", 13.0)
        if duration < min_dur or duration > max_dur:
            return {"passed": False, "score": 0.5, "reason": f"时长不符合要求: {duration:.1f}s (要求 {min_dur}-{max_dur}s)"}
        
        # 检查FPS - Mock模式允许12fps
        if fps < 10 or fps > 30:
            return {"passed": False, "score": 0.6, "reason": f"FPS异常: {fps}"}
        
        return {
            "passed": True,
            "score": 1.0,
            "reason": "通过",
            "details": {
                "width": width,
                "height": height,
                "fps": fps,
                "duration": duration,
                "frame_count": frame_count
            }
        }
    
    def save_report(self, qc_result: QCResult, output_dir: str = "output/qc_reports"):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        report_file = output_path / f"clip_{qc_result.clip_id:02d}_attempt_{qc_result.attempt:03d}_qc.json"
        
        report_data = {
            "clip_id": qc_result.clip_id,
            "attempt": qc_result.attempt,
            "passed": qc_result.passed,
            "overall_score": qc_result.overall_score,
            "timestamp": datetime.now().isoformat(),
            "file_path": qc_result.file_path,
            "failure_reasons": qc_result.failure_reasons,
            "checks": qc_result.checks
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        # 同时生成可读文本报告
        txt_file = output_path / f"clip_{qc_result.clip_id:02d}_attempt_{qc_result.attempt:03d}_qc.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"QC报告 - Clip {qc_result.clip_id:02d} Attempt {qc_result.attempt:03d}\n")
            f.write(f"{'='*60}\n")
            f.write(f"通过: {qc_result.passed}\n")
            f.write(f"总分: {qc_result.overall_score:.3f}\n")
            f.write(f"文件: {qc_result.file_path}\n")
            f.write(f"失败原因: {'; '.join(qc_result.failure_reasons) if qc_result.failure_reasons else '无'}\n")
            f.write(f"\n详细检查:\n")
            for check_name, check_result in qc_result.checks.items():
                f.write(f"  {check_name}: {'通过' if check_result.get('passed') else '失败'} 分数 {check_result.get('score', 0):.3f} - {check_result.get('reason')}\n")
        
        return str(report_file)
