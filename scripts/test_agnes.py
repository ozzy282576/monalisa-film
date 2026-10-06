#!/usr/bin/env python3
"""
测试Agnes客户端 - 单片段测试
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agnes_client.client import AgnesClient
from src.agnes_client.models import AgnesGenerateRequest
from src.qc.qa_report import QAEngine

def main():
    client = AgnesClient()
    qa = QAEngine()
    
    # 测试生成Clip 1，尝试3次
    for attempt in range(1, 4):
        request = AgnesGenerateRequest(
            prompt="1982 Hong Kong rainy night cityscape, animated, neon signs, wet streets, cinematic, Studio Ghibli style",
            duration_seconds=12,
            width=1080,
            height=1920,
            fps=24,
            clip_id=1,
            attempt=attempt
        )
        
        print(f"\n测试 Attempt {attempt}")
        response = client.generate_clip(request)
        print(f"生成完成: {response.local_path}")
        
        qc_result = qa.check_video(response.local_path, 1, attempt)
        print(f"QC结果: 通过={qc_result.passed} 分数={qc_result.overall_score:.3f}")
        print(f"失败原因: {qc_result.failure_reasons}")

if __name__ == "__main__":
    main()
