#!/usr/bin/env python3
"""
一键生成抖音最终成片
包含封面生成、标题、描述
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
import json

def generate_douyin_metadata():
    metadata = {
        "title": "蒙娜丽莎的雨夜 | 1982年香港雨夜，四个想回家的女孩",
        "description": """1982年，香港，雨季。

一辆夜班出租车，亮着空车牌。
四个女孩，只是想回家。

阿兰，22岁，舞厅领舞，包里有TVB报名表
阿洁，31岁，便利店收银，包里有菠萝包和女儿的画
阿云，29岁，洗碗工，刚拿到驾照
阿心，17岁，会考生，借了同学的相机想拍下美好

那卷在柯达冲印店显影的菲林，颜色不对。

本视频为动画演绎，尊重受害者，无血腥无裸露，风格化处理。
谨以此片纪念1982年雨夜中失去生命的四位女性。
愿所有想回家的女孩，都能平安到家。

#林过云 #雨夜屠夫 #香港奇案 #女性安全 #蒙娜丽莎的雨夜 #1982 #香港电影 #动画短片 #真实案件改编
""",
        "tags": ["林过云", "雨夜屠夫", "香港奇案", "女性安全", "蒙娜丽莎的雨夜", "1982", "真实案件", "动画"],
        "cover_text": "蒙娜丽莎的雨夜\n1982 香港雨季 四个想回家的女孩",
        "duration": "3分钟",
        "resolution": "1080x1920 9:16",
        "fps": 24,
        "ethics": "尊重受害者，无血腥，无猎奇，纪念性质"
    }
    
    output_path = Path("output/final/douyin_metadata.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"抖音元数据已生成: {output_path}")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    
    return metadata

if __name__ == "__main__":
    generate_douyin_metadata()
