"""
林过云项目 - 15片段场景定义
每个片段12秒，动画视频，抖音9:16
"""

import json
from pathlib import Path
from typing import List, Dict

class SceneManager:
    def __init__(self, config_path: str = "config/scenes.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.scenes = self.config["scenes"]
    
    def get_scene(self, clip_id: int) -> Dict:
        for scene in self.scenes:
            if scene["id"] == clip_id:
                return scene
        raise ValueError(f"Scene {clip_id} not found")
    
    def get_all_scenes(self) -> List[Dict]:
        return self.scenes
    
    def get_prompt_for_agnes(self, clip_id: int, attempt: int = 1) -> str:
        """
        根据attempt调整prompt，前50次尝试后微调
        借鉴挪威722项目的prompt优化策略
        """
        scene = self.get_scene(clip_id)
        base_prompt = scene["prompt"]
        
        # 尝试次数越多，prompt越精细
        if attempt > 50:
            base_prompt += ", high quality, sharp, no distortion, perfect anatomy, smooth motion"
        if attempt > 100:
            base_prompt += ", 8k, ultra detailed, cinematic lighting"
        if attempt > 150:
            base_prompt += ", flawless, no extra limbs, no warped face, no flicker"
        
        # 添加全局风格
        global_style = self.config.get("style_global", "")
        full_prompt = f"{base_prompt}, {global_style}"
        
        return full_prompt
    
    def get_narration(self, clip_id: int) -> str:
        scene = self.get_scene(clip_id)
        return scene.get("narration", "")
    
    def generate_storyboard_text(self) -> str:
        """生成文字分镜表"""
        storyboard = []
        storyboard.append("# 林过云项目 - 15片段分镜表 (抖音3分钟版)")
        storyboard.append(f"总时长: {self.config['total_duration_seconds']}秒")
        storyboard.append("")
        for scene in self.scenes:
            storyboard.append(f"## Clip {scene['id']:02d} - {scene['title']} ({scene['duration']}s)")
            storyboard.append(f"- Prompt: {scene['prompt']}")
            storyboard.append(f"- 中文: {scene['prompt_cn']}")
            storyboard.append(f"- 旁白: {scene['narration']}")
            storyboard.append(f"- 禁止: {', '.join(scene.get('forbidden', []))}")
            storyboard.append("")
        
        return "\n".join(storyboard)

if __name__ == "__main__":
    manager = SceneManager()
    print(manager.generate_storyboard_text())
