"""
挪威722事件项目参考 - 工作流复用
记录挪威722事件抖音视频项目的成功经验，应用于林过云项目

挪威722事件：2011年7月22日挪威奥斯陆爆炸与于特岛枪击案
该项目已验证的流程：
- 15片段 x 12秒 = 3分钟
- 每片段200次请求重试
- 串行执行避免限流
- 严格QC QA
"""

NORWAY_722_WORKFLOW = {
    "project_name": "挪威722事件 - 抖音纪念视频",
    "total_clips": 15,
    "clip_duration": 12,
    "total_duration": 180,
    "retries_per_clip": 200,
    "execution_mode": "serial",
    "agnes_model": "agnes-video-v3-animated",
    "style": "纪录片动画，尊重受害者，冷色调，北欧极简",
    "qc_pipeline": [
        "distortion_check",
        "flicker_check",
        "continuity_check",
        "nsfw_check",
        "historical_accuracy_check"
    ],
    "lessons_learned": [
        "1. 串行请求比并行更稳定，Agnes API限流为5并发，串行可避免429",
        "2. 200次重试中，前50次畸变率高，需调整prompt，后150次微调seed",
        "3. 动画视频必须检测是否为图片轮播 (frame_diff < 1.0)",
        "4. 抖音对历史事件内容审核严格，需避免血腥，使用象征手法",
        "5. 最终拼接需添加2帧交叉淡化，避免硬切",
        "6. 每个片段生成后立即QC，不通过立即重试，不积压",
        "7. 使用光流检测肢体畸变效果优于姿态估计",
        "8. 保留所有attempt的QC报告，用于分析模型弱点"
    ]
}

def get_norway_workflow_adaptation_for_lam():
    """
    将挪威722流程适配到林过云项目
    """
    adaptation = {
        "相同点": [
            "同样15片段，12秒每段，3分钟总长",
            "同样200次重试，串行执行",
            "同样动画风格非图片轮播",
            "同样严格QC QA，无瑕疵成片",
            "同样尊重受害者，拒绝血腥奇观"
        ],
        "不同点": [
            "挪威722是北欧冷色调，林过云是香港雨夜霓虹暖冷对比",
            "挪威722侧重纪念与反思，林过云侧重女性视角与城市孤独",
            "挪威722有大量空镜，林过云有出租车、暗房等特定符号",
            "林过云项目增加抖音合规检查 (9:16, 24fps, 无血腥)",
            "林过云项目增加蒙娜丽莎隐喻的艺术性检查"
        ],
        "复用代码": [
            "src/agnes_client/client.py - 完全复用，支持mock",
            "src/qc/distortion.py - 复用光流检测逻辑",
            "src/pipeline/orchestrator.py - 复用串行15片段逻辑",
            "config/qc_thresholds.json - 复用阈值配置"
        ]
    }
    return adaptation

if __name__ == "__main__":
    import json
    print("挪威722工作流:")
    print(json.dumps(NORWAY_722_WORKFLOW, ensure_ascii=False, indent=2))
    print("\n适配到林过云:")
    print(json.dumps(get_norway_workflow_adaptation_for_lam(), ensure_ascii=False, indent=2))
