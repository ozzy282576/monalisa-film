#!/usr/bin/env python3
"""
运行完整流水线 - 串行15片段，每片段200次重试
基于挪威722事件流程
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pipeline.orchestrator import PipelineOrchestrator

def main():
    import argparse
    parser = argparse.ArgumentParser(description="蒙娜丽莎的雨夜 - 林过云抖音视频流水线")
    parser.add_argument("--start", type=int, default=1, help="起始片段ID (1-15)")
    parser.add_argument("--end", type=int, default=15, help="结束片段ID (1-15)")
    parser.add_argument("--config", type=str, default="config/agnes_config.json", help="Agnes配置文件")
    parser.add_argument("--mock", action="store_true", help="强制Mock模式 (本地动画生成)")
    
    args = parser.parse_args()
    
    # 如果指定mock，修改配置
    if args.mock:
        import json
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        config["mock_mode"] = True
        with open(args.config, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[Main] 强制Mock模式")
    
    orchestrator = PipelineOrchestrator(config_path=args.config)
    final_video = orchestrator.run(start_clip=args.start, end_clip=args.end)
    
    print("\n" + "="*70)
    print(f"✓ 流水线完成! 最终成片: {final_video}")
    print("="*70)
    print("\n下一步:")
    print(f"1. 查看最终视频: {final_video}")
    print(f"2. 查看QC报告: output/final/final_qc_report.txt")
    print(f"3. 查看流水线报告: output/final/PIPELINE_REPORT.md")
    print(f"4. 上传抖音: 建议添加标签 #林过云 #雨夜屠夫 #香港奇案 #女性安全 #蒙娜丽莎的雨夜")

if __name__ == "__main__":
    main()
