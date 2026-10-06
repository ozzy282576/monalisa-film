"""
Agnes Video Generation Client
- 支持真实API调用 (当配置 AGNES_API_KEY)
- 支持Mock动画生成 (本地生成动画视频，用于QC测试和无API环境)
- 串行请求，单片段200次重试，15片段串行

基于挪威722事件项目的Agnes客户端改编
"""

import os
import time
import json
import random
import hashlib
from pathlib import Path
from typing import Optional
import requests

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .models import AgnesGenerateRequest, AgnesGenerateResponse, ClipStatus
from .exceptions import AgnesAPIError, AgnesTimeoutError

# 尝试获取ffmpeg
try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG_BIN = "ffmpeg"

class AgnesClient:
    def __init__(self, config_path: str = "config/agnes_config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.base_url = self.config.get("base_url", "https://api.agnes.ai/v1")
        self.api_key = os.getenv(self.config.get("api_key_env", "AGNES_API_KEY"))
        self.mock_mode = self.config.get("mock_mode", True)
        # 只有当配置为非Mock且没有Key时，才回退到Mock；如果配置为Mock，即使有Key也尊重配置
        # 这样可以通过 --mock 参数强制Mock，或通过配置强制真实
        if not self.mock_mode and not (self.api_key and len(self.api_key) > 10):
            print(f"[AgnesClient] 警告: 配置为真实模式但未找到AGNES_API_KEY，回退到Mock模式")
            self.mock_mode = True
        
        self.output_dir = Path("output/clips")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[AgnesClient] 初始化 - Mock模式: {self.mock_mode}, BaseURL: {self.base_url}, 模型: {self.config.get('model')}")
        if not self.mock_mode:
            print(f"[AgnesClient] 使用真实API, Key: {self.api_key[:8]}... 风格: {self.config.get('style_preset')}")
        else:
            print(f"[AgnesClient] 使用Mock 3D动画生成 (本地OpenCV，真实API不可用或被强制Mock)")
    
    def generate_clip(self, request: AgnesGenerateRequest) -> AgnesGenerateResponse:
        """
        生成单个片段，单次请求
        """
        start_time = time.time()
        
        if self.mock_mode:
            return self._mock_generate(request, start_time)
        else:
            return self._real_generate(request, start_time)
    
    def _real_generate(self, request: AgnesGenerateRequest, start_time: float) -> AgnesGenerateResponse:
        """
        真实Agnes API调用
        流程：POST /video/generate -> polling /video/status/{task_id} -> download
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "duration": request.duration_seconds,
            "width": request.width,
            "height": request.height,
            "fps": request.fps,
            "aspect_ratio": request.aspect_ratio,
            "style": request.style_preset,
            "model": request.model,
            "seed": request.seed or random.randint(0, 2**32-1)
        }
        
        try:
            # 1. 提交任务
            resp = requests.post(f"{self.base_url}/video/generate", json=payload, headers=headers, timeout=30)
            if resp.status_code == 429:
                raise AgnesAPIError("Rate limited")
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("task_id") or data.get("id")
            
            # 2. 轮询
            timeout = self.config.get("timeout_seconds", 120)
            poll_interval = self.config.get("poll_interval_seconds", 3)
            elapsed = 0
            while elapsed < timeout:
                time.sleep(poll_interval)
                elapsed += poll_interval
                status_resp = requests.get(f"{self.base_url}/video/status/{task_id}", headers=headers, timeout=15)
                status_resp.raise_for_status()
                status_data = status_resp.json()
                status = status_data.get("status")
                if status == "completed":
                    video_url = status_data.get("video_url") or status_data.get("url")
                    # 下载
                    local_path = self._download_video(video_url, request.clip_id, request.attempt)
                    return AgnesGenerateResponse(
                        task_id=task_id,
                        status=ClipStatus.COMPLETED,
                        clip_id=request.clip_id,
                        attempt=request.attempt,
                        video_url=video_url,
                        local_path=local_path,
                        prompt_used=request.prompt,
                        generation_time_seconds=time.time() - start_time,
                        metadata=status_data
                    )
                elif status == "failed":
                    raise AgnesAPIError(f"Generation failed: {status_data}")
            
            raise AgnesTimeoutError(f"Task {task_id} timeout after {timeout}s")
            
        except Exception as e:
            raise AgnesAPIError(f"Agnes API error: {e}") from e
    
    def _mock_generate(self, request: AgnesGenerateRequest, start_time: float) -> AgnesGenerateResponse:
        """
        Mock动画生成 - 生成真正的动画视频而非图片轮播
        使用OpenCV生成风格化动画，模拟AI视频生成的不完美性，用于测试QC流程
        """
        # 生成唯一文件名
        task_id = f"mock_{request.clip_id}_{request.attempt}_{hashlib.md5(request.prompt.encode()).hexdigest()[:8]}"
        output_path = self.output_dir / f"clip_{request.clip_id:02d}_attempt_{request.attempt:03d}.mp4"
        
        # 根据clip_id生成不同风格动画
        self._generate_animated_clip(
            output_path=output_path,
            clip_id=request.clip_id,
            attempt=request.attempt,
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            fps=request.fps,
            duration=request.duration_seconds
        )
        
        # 模拟API延迟 - Mock模式减少
        time.sleep(random.uniform(0.1, 0.3))
        
        return AgnesGenerateResponse(
            task_id=task_id,
            status=ClipStatus.COMPLETED,
            clip_id=request.clip_id,
            attempt=request.attempt,
            video_url=None,
            local_path=str(output_path),
            prompt_used=request.prompt,
            generation_time_seconds=time.time() - start_time,
            metadata={"mock": True, "seed": request.seed}
        )
    
    def _generate_animated_clip(self, output_path: Path, clip_id: int, attempt: int, prompt: str, width: int, height: int, fps: int, duration: int):
        """
        生成真正的动画视频 (非图片轮播)
        每个clip_id有不同的动画逻辑
        优化版：Mock模式使用半分辨率和优化绘制
        """
        # Mock模式优化：半分辨率 + 12fps 以加速，仍满足抖音9:16合规 (QC允许540x960)
        if self.mock_mode:
            width = width // 2
            height = height // 2
            fps = 12  # 降低fps加速，但保持动画感
        
        total_frames = fps * duration
        w, h = width, height
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))
        
        # 根据clip_id选择动画主题色
        themes = {
            1: {"bg": (20, 25, 40), "accent": (255, 180, 80)},   # 雨夜蓝+霓虹橙
            2: {"bg": (15, 15, 15), "accent": (80, 255, 180)},  # 车内黑+仪表绿
            3: {"bg": (40, 30, 50), "accent": (255, 200, 200)}, # 电话亭紫+暖光
            4: {"bg": (60, 10, 10), "accent": (255, 50, 50)},    # 暗房红
            5: {"bg": (30, 30, 30), "accent": (220, 220, 180)}, # 报纸黄
            6: {"bg": (50, 40, 20), "accent": (255, 230, 150)}, # 便利店暖黄
            7: {"bg": (20, 40, 50), "accent": (150, 255, 255)}, # 法医室冷蓝
            8: {"bg": (40, 35, 60), "accent": (255, 180, 255)}, # 驾照紫
            9: {"bg": (10, 10, 20), "accent": (200, 200, 255)}, # 后视镜
            10: {"bg": (30, 50, 40), "accent": (180, 255, 180)},# 少女绿
            11: {"bg": (70, 15, 15), "accent": (255, 100, 100)},# 震惊红
            12: {"bg": (25, 30, 45), "accent": (100, 180, 255)},# 雨后蓝
            13: {"bg": (45, 40, 35), "accent": (255, 220, 180)},# 纪念暖
            14: {"bg": (15, 20, 35), "accent": (255, 200, 100)},# 空车
            15: {"bg": (5, 5, 5), "accent": (255, 255, 255)},   # 黑白
        }
        theme = themes.get(clip_id, {"bg": (30, 30, 40), "accent": (200, 200, 255)})
        
        # 随机种子影响畸变，attempt越高畸变越少 (模拟200次重试优化)
        distortion_factor = max(0.01, 1.0 - (attempt / 200.0) * 0.95)  # attempt 1时畸变大，200时几乎无畸变
        
        # 预计算一些运动轨迹以增加帧差
        np.random.seed(clip_id * 1000 + attempt)
        
        for frame_idx in range(total_frames):
            # 创建背景，添加轻微颜色变化以增加帧差
            base_color = np.array(theme["bg"], dtype=np.float32)
            # 随时间轻微变化
            color_shift = np.sin(frame_idx * 0.1) * 5
            bg_color = np.clip(base_color + color_shift, 0, 255).astype(np.uint8)
            frame = np.full((h, w, 3), bg_color, dtype=np.uint8)
            
            t = frame_idx / total_frames  # 0-1
            
            # 根据clip_id生成不同动画
            if clip_id == 1:  # 雨夜城市
                # 霓虹灯闪烁 - 优化减少绘制
                for i in range(3):
                    x = int((w * 0.3 * i + t * 80) % w)
                    y = int(h * 0.15 + i * 60 + np.sin(t*3 + i)*8)
                    cv2.rectangle(frame, (x, y), (x+80, y+12), theme["accent"], -1)
                # 雨线 - 减少数量
                for _ in range(25):
                    rx = random.randint(0, w-1)
                    ry = int((random.randint(0, h-1) + t * 300) % h)
                    cv2.line(frame, (rx, ry), (rx+2, ry+8), (200, 200, 255), 1)
            
            elif clip_id == 2:  # 出租车内部
                # 仪表盘
                cv2.circle(frame, (w//2, h//2), int(100 + np.sin(t*2)*5), theme["accent"], 2)
                # 雨刷
                angle = np.sin(t * 6) * 60
                x1, y1 = w//2, h//3
                x2 = int(x1 + 200 * np.cos(np.radians(angle)))
                y2 = int(y1 + 200 * np.sin(np.radians(angle)))
                cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 3)
                # 雨 - 减少
                for _ in range(12):
                    rx = random.randint(0, w-1)
                    ry = random.randint(0, h-1)
                    cv2.circle(frame, (rx, ry), 1, (150, 150, 255), -1)
            
            elif clip_id == 3:  # 阿兰
                # 电话亭
                cv2.rectangle(frame, (w//4, h//4), (w*3//4, h*3//4), (80, 80, 100), -1)
                # 人物剪影微笑
                cx, cy = w//2 + int(np.sin(t*1.5)*8), h//2
                cv2.circle(frame, (cx, cy), 50, (60, 50, 70), -1)  # 头
                # 蒙娜丽莎微笑曲线
                smile_y = cy + 20 + int(np.sin(t*2)*2)
                cv2.ellipse(frame, (cx, smile_y), (18, 7), 0, 0, 180, theme["accent"], 2)
                # 雨
                for _ in range(10):
                    rx = random.randint(0, w-1)
                    ry = int((random.randint(0, h-1) + t*200) % h)
                    cv2.line(frame, (rx, ry), (rx, ry+6), (200, 200, 255), 1)
            
            elif clip_id == 4:  # 暗房 - 修复版：降低红色占比，避免NSFW误判
                # 红光渐显，但使用更平衡的颜色，减少纯红
                intensity = int(80 + t*40)  # 80-120，减少变化范围降低闪烁
                # 使用暗红+暖黄混合，而非纯红
                frame[:] = (20, 15, intensity)  # BGR: 20,15,intensity -> 暗红带一点蓝
                # 相纸中图像浮现 - 使用米黄而非红色
                alpha = t
                # 相纸颜色改为暖白
                paper_color = (int(180+40*alpha), int(160+30*alpha), int(140+20*alpha))
                cv2.rectangle(frame, (w//4, h//3), (w*3//4, h*2//3), paper_color, -1)
                # 添加显影液波纹
                wave_y = int(h//2 + np.sin(t*3)*10)
                cv2.line(frame, (w//4, wave_y), (w*3//4, wave_y), (100, 80, 60), 1)
                # 气泡
                for _ in range(4):
                    bx = random.randint(w//4, w*3//4)
                    by = random.randint(h//3, h*2//3)
                    br = random.randint(2, 6)
                    cv2.circle(frame, (bx, by), br, (100, 100, 255), 1)
            
            elif clip_id in [5,6,7,8,9,10,11,12,13,14,15]:
                # 通用动画模板 - 增强运动版
                # 减少噪点计算频率
                if frame_idx % 3 == 0:
                    noise = np.random.randint(0, 15, (h, w, 3), dtype=np.uint8)
                    frame = cv2.add(frame, noise)
                
                # 中心形状动画 + 额外运动元素确保帧差
                cx, cy = w//2 + int(np.sin(t*3)*20), h//2 + int(np.cos(t*2)*10)
                # 模拟畸变：attempt低时形状扭曲
                if distortion_factor > 0.3 and random.random() < distortion_factor * 0.08:
                    cx += random.randint(-30, 30)
                    cy += random.randint(-30, 30)
                    if random.random() < 0.03:
                        cv2.circle(frame, (cx+60, cy), 15, theme["accent"], -1)
                
                # 主体 - 脉动圆
                radius = int(40 + np.sin(t*5)*20 + np.sin(t*2)*10)
                cv2.circle(frame, (cx, cy), radius, theme["accent"], 2)
                
                # 运动元素：横移光斑
                light_x = int((t * w * 1.5) % (w + 100) - 50)
                light_y = h//4 + int(np.sin(t*4)*20)
                cv2.circle(frame, (light_x, light_y), 8, (255,255,255), -1)
                
                # 额外动画元素根据clip_id
                if clip_id == 5:
                    cv2.rectangle(frame, (w//4, h//3), (w*3//4, h*2//3), (200,200,180), 1)
                    # 报纸标题线
                    for i in range(3):
                        y = h//3 + 20 + i*15
                        cv2.line(frame, (w//4+10, y), (w*3//4-10, y), (180,180,160), 1)
                elif clip_id == 6:
                    cv2.rectangle(frame, (w//3, h//3), (w*2//3, h//2), theme["accent"], -1)
                elif clip_id == 7:
                    cv2.line(frame, (w//4, h//2), (w*3//4, h//2), theme["accent"], 2)
                    # 地图点
                    for i in range(4):
                        px = w//4 + i*(w//2)//3 + int(np.sin(t*2+i)*5)
                        py = h//2 + int(np.cos(t*3+i)*8)
                        cv2.circle(frame, (px, py), 5, (255,100,100), -1)
                elif clip_id == 15:
                    # 黑白文字区域
                    pass
            
            # 添加胶片颗粒 - 降低强度 (仅偶尔)
            if distortion_factor > 0.2 and frame_idx % 5 == 0:
                # 使用更轻量的噪点
                noise = np.random.randint(-5, 5, (h, w, 3), dtype=np.int16)
                frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            
            # 暗角效果 - 简化版，避免大sigma高斯模糊
            if clip_id != 15 and frame_idx % 2 == 0:
                # 简单暗角：边缘压暗
                # 使用线性渐变而非高斯模糊
                pass  # 跳过以提升速度
            
            # 确保帧格式正确
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)
            if frame.shape[0] != h or frame.shape[1] != w:
                frame = cv2.resize(frame, (w, h))
            
            # 添加时间码水印用于QC
            cv2.putText(frame, f"C{clip_id:02d} A{attempt:03d} F{frame_idx}", (10, h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)
            
            try:
                out.write(frame)
            except Exception as e:
                print(f"[Mock] 写入帧失败 {frame_idx}: {e}")
                continue
        
        out.release()
        # 验证文件
        if not output_path.exists() or output_path.stat().st_size < 1024:
            print(f"[Mock] 警告: 生成文件过小或不存在: {output_path}")
        else:
            print(f"[Mock] 生成动画片段 C{clip_id:02d} Attempt {attempt:03d} -> {output_path} ({output_path.stat().st_size//1024}KB, 畸变因子: {distortion_factor:.3f})")
    
    def _download_video(self, url: str, clip_id: int, attempt: int) -> str:
        output_path = self.output_dir / f"clip_{clip_id:02d}_attempt_{attempt:03d}.mp4"
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return str(output_path)
    
    def __init_subclass__(cls) -> None:
        pass
