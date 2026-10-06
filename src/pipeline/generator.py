"""
单片段生成器 - 200次重试 + QC
基于挪威722项目的重试逻辑
"""

import time
import random
from pathlib import Path
from typing import Optional

from ..agnes_client.client import AgnesClient
from ..agnes_client.models import AgnesGenerateRequest, ClipResult
from ..agnes_client.exceptions import AgnesQCFailedError
from ..qc.qa_report import QAEngine
from ..scenes.lin_guoyun_scenes import SceneManager

class ClipGenerator:
    def __init__(self, agnes_client: AgnesClient, qa_engine: QAEngine, scene_manager: SceneManager):
        self.agnes_client = agnes_client
        self.qa_engine = qa_engine
        self.scene_manager = scene_manager
        self.max_retries = agnes_client.config.get("max_retries_per_clip", 200)
    
    def generate_single_clip_with_retry(self, clip_id: int) -> ClipResult:
        """
        生成单个片段，200次重试直到QC通过
        串行逻辑的核心
        """
        scene = self.scene_manager.get_scene(clip_id)
        title = scene["title"]
        
        print(f"\n{'='*70}")
        print(f"[Generator] 开始生成 Clip {clip_id:02d} - {title}")
        print(f"[Generator] 最大重试: {self.max_retries}次")
        print(f"{'='*70}")
        
        best_result = None
        best_score = -1
        history = []
        
        for attempt in range(1, self.max_retries + 1):
            print(f"\n[Generator] Clip {clip_id:02d} - Attempt {attempt:03d}/{self.max_retries}")
            
            # 生成prompt (随attempt优化)
            prompt = self.scene_manager.get_prompt_for_agnes(clip_id, attempt)
            
            # 构建请求
            request = AgnesGenerateRequest(
                prompt=prompt,
                prompt_cn=scene.get("prompt_cn"),
                duration_seconds=scene.get("duration", 12),
                width=self.agnes_client.config.get("resolution", {}).get("width", 1080),
                height=self.agnes_client.config.get("resolution", {}).get("height", 1920),
                fps=self.agnes_client.config.get("fps", 24),
                aspect_ratio=self.agnes_client.config.get("aspect_ratio", "9:16"),
                style_preset=self.agnes_client.config.get("style_preset", "noir_animation"),
                model=self.agnes_client.config.get("model", "agnes-video-v3-animated"),
                clip_id=clip_id,
                attempt=attempt,
                seed=random.randint(0, 2**32-1) if attempt > 1 else 42  # 首次固定seed便于复现
            )
            
            try:
                # 调用Agnes生成
                response = self.agnes_client.generate_clip(request)
                history.append(response)
                
                # QC检查
                qc_result = self.qa_engine.check_video(response.local_path, clip_id, attempt)
                
                # 保存QC报告
                report_path = self.qa_engine.save_report(qc_result)
                
                # 更新最佳结果
                if qc_result.overall_score > best_score:
                    best_score = qc_result.overall_score
                    best_result = (response, qc_result)
                    print(f"[Generator] 新最佳分数: {best_score:.3f} (Attempt {attempt})")
                
                # 如果通过，直接返回
                if qc_result.passed:
                    print(f"[Generator] ✓ Clip {clip_id:02d} 在 Attempt {attempt:03d} 通过QC! 分数: {qc_result.overall_score:.3f}")
                    
                    # 移动最佳文件到最终位置
                    final_path = Path(f"output/clips/final_clip_{clip_id:02d}.mp4")
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    # 复制文件
                    import shutil
                    shutil.copy(response.local_path, final_path)
                    
                    return ClipResult(
                        clip_id=clip_id,
                        title=title,
                        final_path=str(final_path),
                        best_attempt=attempt,
                        total_attempts=attempt,
                        qc_result=qc_result,
                        generation_history=history
                    )
                else:
                    print(f"[Generator] ✗ Attempt {attempt:03d} QC失败: {qc_result.failure_reasons}")
                    # 如果是图片轮播，立即调整prompt
                    if any("图片轮播" in reason for reason in qc_result.failure_reasons):
                        print(f"[Generator] 检测到图片轮播，下一次尝试将增强动画提示")
                
            except Exception as e:
                print(f"[Generator] Attempt {attempt:03d} 异常: {e}")
                # 继续重试
            
            # 避免过快请求，模拟真实API限流
            if attempt % 10 == 0:
                print(f"[Generator] 已尝试 {attempt} 次，最佳分数: {best_score:.3f}")
            
            # 短暂休眠，避免CPU过热 (真实环境是等待API)
            time.sleep(0.1)
        
        # 200次后仍未通过，返回最佳结果或抛出异常
        if best_result:
            response, qc_result = best_result
            print(f"[Generator] ! Clip {clip_id:02d} 200次后未完全通过，返回最佳结果 分数: {best_score:.3f}")
            # 即使未完全通过，也保存最佳
            final_path = Path(f"output/clips/final_clip_{clip_id:02d}_best.mp4")
            import shutil
            shutil.copy(response.local_path, final_path)
            
            return ClipResult(
                clip_id=clip_id,
                title=title,
                final_path=str(final_path),
                best_attempt=qc_result.attempt,
                total_attempts=self.max_retries,
                qc_result=qc_result,
                generation_history=history
            )
        else:
            raise AgnesQCFailedError(clip_id, self.max_retries, None)
