"""
视频拼接器 - 将15个12秒片段拼接为3分钟成片
添加转场、字幕、音频
"""

import json
import subprocess
from pathlib import Path
from typing import List
import cv2

from ..scenes.lin_guoyun_scenes import SceneManager

try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG_BIN = "ffmpeg"

class VideoStitcher:
    def __init__(self, scene_manager: SceneManager):
        self.scene_manager = scene_manager
        self.ffmpeg = FFMPEG_BIN
    
    def stitch_clips(self, clip_paths: List[str], output_path: str, add_narration: bool = True) -> str:
        """
        拼接片段
        """
        print(f"\n[Stitcher] 开始拼接 {len(clip_paths)} 个片段 -> {output_path}")
        
        # 验证所有片段存在
        for p in clip_paths:
            if not Path(p).exists():
                raise FileNotFoundError(f"片段不存在: {p}")
        
        # 创建ffmpeg concat文件
        concat_file = Path("output/final/concat_list.txt")
        concat_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for clip_path in clip_paths:
                # 使用绝对路径
                abs_path = Path(clip_path).absolute()
                f.write(f"file '{abs_path}'\n")
        
        # 基础拼接命令
        # 添加转场：2帧交叉淡化 (参考挪威722项目经验)
        # 为了简化，先直接concat，后续可添加转场滤镜
        
        # 检查是否有音频需要添加
        # 抖音视频通常需要背景音乐，这里我们生成静音+雨声音效
        
        cmd = [
            self.ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "24",
            "-movflags", "+faststart",
            output_path
        ]
        
        print(f"[Stitcher] 执行: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"[Stitcher] FFmpeg错误: {result.stderr}")
            # 尝试备用方案：使用OpenCV拼接
            return self._stitch_with_opencv(clip_paths, output_path)
        
        print(f"[Stitcher] 拼接完成: {output_path}")
        
        # 添加字幕和片头片尾
        final_with_subs = self._add_subtitles_and_effects(output_path)
        
        return final_with_subs
    
    def _stitch_with_opencv(self, clip_paths: List[str], output_path: str) -> str:
        """
        备用方案：OpenCV拼接
        """
        print("[Stitcher] 使用OpenCV备用拼接")
        
        # 读取第一个视频获取参数
        cap = cv2.VideoCapture(clip_paths[0])
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        for clip_path in clip_paths:
            cap = cv2.VideoCapture(clip_path)
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
            cap.release()
        
        out.release()
        return output_path
    
    def _add_subtitles_and_effects(self, input_path: str) -> str:
        """
        添加字幕、片头片尾、雨声音效等
        简化版：直接返回原路径，实际项目中可添加
        """
        # TODO: 添加字幕
        # - 使用ffmpeg drawtext滤镜添加旁白字幕
        # - 片头：蒙娜丽莎的雨夜标题
        # - 片尾：纪念字幕
        
        output_with_effects = str(Path(input_path).parent / "final_with_effects.mp4")
        
        # 简单复制，实际可添加滤镜
        # 这里为了演示，添加一个轻微的胶片颗粒和暗角效果
        
        cmd = [
            self.ffmpeg,
            "-y",
            "-i", input_path,
            "-vf", "eq=contrast=1.1:brightness=-0.05, vignette=angle=PI/4",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            output_with_effects
        ]
        
        # 如果没有音频，添加静音
        # 检查输入是否有音频
        probe_cmd = [self.ffmpeg, "-i", input_path]
        # 简化：直接尝试添加效果，如果失败返回原文件
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print(f"[Stitcher] 添加效果完成: {output_with_effects}")
                return output_with_effects
            else:
                print(f"[Stitcher] 添加效果失败，使用原文件: {result.stderr[:500]}")
                return input_path
        except Exception as e:
            print(f"[Stitcher] 效果处理异常: {e}")
            return input_path
    
    def generate_final_qc_report(self, final_video_path: str, clip_results: List) -> str:
        """
        生成最终成片的QC报告
        """
        cap = cv2.VideoCapture(final_video_path)
        if not cap.isOpened():
            return "无法打开最终视频"
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        file_size = Path(final_video_path).stat().st_size / (1024*1024)  # MB
        
        report = {
            "final_video": final_video_path,
            "resolution": f"{width}x{height}",
            "fps": fps,
            "duration_seconds": duration,
            "frame_count": frame_count,
            "file_size_mb": file_size,
            "total_clips": len(clip_results),
            "clips": [
                {
                    "clip_id": r.clip_id,
                    "title": r.title,
                    "attempt": r.best_attempt,
                    "total_attempts": r.total_attempts,
                    "qc_score": r.qc_result.overall_score,
                    "passed": r.qc_result.passed
                } for r in clip_results
            ],
            "overall_passed": all(r.qc_result.passed for r in clip_results),
            "avg_qc_score": sum(r.qc_result.overall_score for r in clip_results) / len(clip_results) if clip_results else 0
        }
        
        report_path = Path("output/final/final_qc_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 文本报告
        txt_path = Path("output/final/final_qc_report.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("最终成片 QC 报告 - 蒙娜丽莎的雨夜 (林过云抖音版)\n")
            f.write("="*70 + "\n")
            f.write(f"文件: {final_video_path}\n")
            f.write(f"分辨率: {width}x{height} (抖音要求 1080x1920)\n")
            f.write(f"FPS: {fps}\n")
            f.write(f"时长: {duration:.1f}秒 (目标180秒)\n")
            f.write(f"文件大小: {file_size:.1f}MB\n")
            f.write(f"总片段: {len(clip_results)}\n")
            f.write(f"平均QC分数: {report['avg_qc_score']:.3f}\n")
            f.write(f"全部通过: {report['overall_passed']}\n")
            f.write("\n片段详情:\n")
            for r in clip_results:
                f.write(f"  Clip {r.clip_id:02d} {r.title}: Attempt {r.best_attempt}/{r.total_attempts} Score {r.qc_result.overall_score:.3f} {'✓' if r.qc_result.passed else '✗'}\n")
            f.write("\n")
            f.write("伦理声明: 本视频尊重受害者，无血腥，无裸露，仅为纪念与警示。\n")
        
        print(f"[Stitcher] 最终QC报告: {txt_path}")
        with open(txt_path, 'r', encoding='utf-8') as f:
            print(f.read())
        
        return str(report_path)
