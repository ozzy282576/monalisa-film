"""
主流水线 - 串行15片段，每片段200次重试
基于挪威722事件验证的串行流程
"""

import json
import time
from pathlib import Path
from typing import List

from ..agnes_client.client import AgnesClient
from ..qc.qa_report import QAEngine
from ..scenes.lin_guoyun_scenes import SceneManager
from .generator import ClipGenerator
from .stitcher import VideoStitcher
from ..agnes_client.models import ClipResult

class PipelineOrchestrator:
    def __init__(self, config_path: str = "config/agnes_config.json"):
        print("="*70)
        print("蒙娜丽莎的雨夜 - 林过云抖音视频生成流水线")
        print("基于挪威722事件项目流程")
        print("="*70)
        print(f"配置: {config_path}")
        
        self.agnes_client = AgnesClient(config_path)
        self.qa_engine = QAEngine()
        self.scene_manager = SceneManager()
        self.generator = ClipGenerator(self.agnes_client, self.qa_engine, self.scene_manager)
        self.stitcher = VideoStitcher(self.scene_manager)
        
        self.total_clips = self.agnes_client.config.get("total_clips", 15)
        self.clip_duration = self.agnes_client.config.get("clip_duration_seconds", 12)
        
        print(f"总片段: {self.total_clips} x {self.clip_duration}秒 = {self.total_clips * self.clip_duration}秒")
        print(f"每片段最大重试: {self.agnes_client.config.get('max_retries_per_clip', 200)}")
        print(f"执行模式: {'串行' if self.agnes_client.config.get('serial_execution') else '并行'}")
        print(f"Mock模式: {self.agnes_client.config.get('mock_mode')}")
    
    def run(self, start_clip: int = 1, end_clip: int = 15) -> str:
        """
        运行完整流水线
        串行15个片段请求
        """
        print(f"\n[Orchestrator] 开始执行 Clip {start_clip} 到 {end_clip}")
        
        clip_results: List[ClipResult] = []
        failed_clips = []
        
        total_start_time = time.time()
        
        for clip_id in range(start_clip, end_clip + 1):
            clip_start = time.time()
            try:
                result = self.generator.generate_single_clip_with_retry(clip_id)
                clip_results.append(result)
                elapsed = time.time() - clip_start
                print(f"\n[Orchestrator] ✓ Clip {clip_id:02d} 完成，耗时 {elapsed:.1f}s，最佳尝试 {result.best_attempt}")
                
                # 保存中间进度
                self._save_progress(clip_results, failed_clips)
                
            except Exception as e:
                print(f"\n[Orchestrator] ✗ Clip {clip_id:02d} 失败: {e}")
                failed_clips.append({"clip_id": clip_id, "error": str(e)})
                self._save_progress(clip_results, failed_clips)
                # 根据配置决定是否继续
                # 这里选择继续，尽量完成所有片段
                continue
        
        total_elapsed = time.time() - total_start_time
        
        print(f"\n{'='*70}")
        print(f"[Orchestrator] 所有片段生成完成")
        print(f"成功: {len(clip_results)}/{self.total_clips}")
        print(f"失败: {len(failed_clips)}")
        print(f"总耗时: {total_elapsed/60:.1f}分钟")
        print(f"{'='*70}")
        
        if not clip_results:
            raise RuntimeError("所有片段均失败，无法拼接")
        
        # 按clip_id排序
        clip_results.sort(key=lambda x: x.clip_id)
        clip_paths = [r.final_path for r in clip_results]
        
        # 拼接最终视频
        final_output = "output/final/monalisa_lam_3min_douyin_final.mp4"
        final_video = self.stitcher.stitch_clips(clip_paths, final_output)
        
        # 最终QC
        self.stitcher.generate_final_qc_report(final_video, clip_results)
        
        # 生成最终报告
        self._generate_final_report(clip_results, failed_clips, final_video, total_elapsed)
        
        return final_video
    
    def _save_progress(self, clip_results: List[ClipResult], failed_clips: List):
        progress = {
            "timestamp": time.time(),
            "completed_clips": len(clip_results),
            "total_clips": self.total_clips,
            "failed_clips": failed_clips,
            "clips": [
                {
                    "clip_id": r.clip_id,
                    "title": r.title,
                    "final_path": r.final_path,
                    "best_attempt": r.best_attempt,
                    "total_attempts": r.total_attempts,
                    "qc_score": r.qc_result.overall_score,
                    "passed": r.qc_result.passed
                } for r in clip_results
            ]
        }
        
        progress_path = Path("output/final/progress.json")
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with open(progress_path, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    
    def _generate_final_report(self, clip_results: List[ClipResult], failed_clips: List, final_video: str, total_elapsed: float):
        report_path = Path("output/final/PIPELINE_REPORT.md")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 蒙娜丽莎的雨夜 - 流水线最终报告\n\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"## 总览\n")
            f.write(f"- 总片段: {self.total_clips}\n")
            f.write(f"- 成功: {len(clip_results)}\n")
            f.write(f"- 失败: {len(failed_clips)}\n")
            f.write(f"- 总耗时: {total_elapsed/60:.1f}分钟\n")
            f.write(f"- 最终视频: {final_video}\n")
            f.write(f"- 平均QC分数: {sum(r.qc_result.overall_score for r in clip_results)/len(clip_results):.3f}\n\n")
            
            f.write(f"## 片段详情\n\n")
            f.write(f"| Clip | 标题 | 最佳尝试 | 总尝试 | QC分数 | 通过 |\n")
            f.write(f"|------|------|----------|--------|--------|------|\n")
            for r in clip_results:
                f.write(f"| {r.clip_id:02d} | {r.title} | {r.best_attempt} | {r.total_attempts} | {r.qc_result.overall_score:.3f} | {'✓' if r.qc_result.passed else '✗'} |\n")
            
            f.write(f"\n## 失败片段\n\n")
            if failed_clips:
                for fail in failed_clips:
                    f.write(f"- Clip {fail['clip_id']}: {fail['error']}\n")
            else:
                f.write(f"无失败片段\n")
            
            f.write(f"\n## QC QA 校验\n\n")
            f.write(f"- 畸变检查: 检测肢体畸变、面部扭曲、光流异常\n")
            f.write(f"- 闪烁检查: 亮度方差、闪烁频率\n")
            f.write(f"- 连续性: SSIM、场景跳变\n")
            f.write(f"- NSFW: 血腥、裸露\n")
            f.write(f"- 抖音合规: 9:16, 1080x1920, 24fps, 12秒\n\n")
            
            f.write(f"## 伦理声明\n\n")
            f.write(f"本视频基于真实案件改编，但尊重受害者，无血腥、无裸露、无分尸画面。\n")
            f.write(f"旨在纪念1982年雨夜中想回家的四位女性，警示夜归安全。\n")
            f.write(f"所有女性角色均为风格化动画，非写实真人，尊重不色情。\n\n")
            
            f.write(f"## 技术栈\n\n")
            f.write(f"- Agnes Video v3 Animated (Mock模式: {self.agnes_client.config.get('mock_mode')})\n")
            f.write(f"- OpenCV畸变检测 (光流异常、模糊检测)\n")
            f.write(f"- FFmpeg拼接 (imageio-ffmpeg)\n")
            f.write(f"- 串行15片段，每片段200次重试\n")
            f.write(f"- 基于挪威722事件验证流程\n")
        
        print(f"[Orchestrator] 最终报告: {report_path}")

if __name__ == "__main__":
    orchestrator = PipelineOrchestrator()
    final_video = orchestrator.run()
    print(f"\n最终成片: {final_video}")
