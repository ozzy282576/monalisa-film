"""
Agnes Video Generation Models
基于挪威722事件项目的数据模型，适配林过云项目
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class ClipStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    QC_FAILED = "qc_failed"

class AgnesGenerateRequest(BaseModel):
    prompt: str
    prompt_cn: Optional[str] = None
    duration_seconds: int = 12
    width: int = 1080
    height: int = 1920
    fps: int = 24
    aspect_ratio: str = "9:16"
    style_preset: str = "noir_animation"
    model: str = "agnes-video-v3-animated"
    negative_prompt: str = "blood, gore, real person, photorealistic corpse, explicit nudity, dismemberment, low quality, blurry, distorted limbs, extra fingers, warped face"
    seed: Optional[int] = None
    clip_id: int
    attempt: int = 1

class AgnesGenerateResponse(BaseModel):
    task_id: str
    status: ClipStatus
    clip_id: int
    attempt: int
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    prompt_used: str
    generation_time_seconds: float = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class QCResult(BaseModel):
    clip_id: int
    attempt: int
    passed: bool
    overall_score: float
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    distortion_score: float = 0
    flicker_score: float = 0
    continuity_score: float = 0
    nsfw_score: float = 0
    file_path: str
    failure_reasons: List[str] = Field(default_factory=list)

class ClipResult(BaseModel):
    clip_id: int
    title: str
    final_path: str
    best_attempt: int
    total_attempts: int
    qc_result: QCResult
    generation_history: List[AgnesGenerateResponse] = Field(default_factory=list)
