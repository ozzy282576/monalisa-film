import json
import os
import sys
import time
import requests
import traceback
from pathlib import Path

print("=== 视频生成自动化脚本启动 ===", flush=True)

api_key = os.getenv("ZHIPUAI_API_KEY")
prompt = os.getenv("INPUT_PROMPT")

# Backward-compatible dispatch shim: the generic workflow is registered on the
# default branch, while project-specific workflows may exist only on a production
# branch. A structured prompt can route that registered workflow to this branch's
# full Chessboard64 pipeline; ordinary natural-language prompts still use the
# original one-shot generator below.
def route_chessboard64(raw_prompt):
    try:
        dispatch = json.loads(raw_prompt) if raw_prompt else None
    except (json.JSONDecodeError, TypeError):
        dispatch = None
    if not isinstance(dispatch, dict) or dispatch.get("project") != "chessboard64":
        return False
    if dispatch.get("probe") is True:
        print("CHESSBOARD64_DISPATCH_PROBE_OK", flush=True)
        sys.exit(0)
    payload = dispatch.get("payload", {})
    if not isinstance(payload, dict):
        print("❌ chessboard64 payload must be a JSON object", flush=True)
        sys.exit(2)
    generator = Path(__file__).resolve().parents[1] / "production/chessboard64/generate_cogvideox.py"
    child_argv = [sys.executable, str(generator), "--publish", "--payload",
                  json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]
    print("Routing to production/chessboard64/generate_cogvideox.py", flush=True)
    os.execv(sys.executable, child_argv)
    return True

if (not prompt and os.getenv("GITHUB_REF_NAME") == "arena/56672981-monalisa-film"):
    request_file = Path("production/chessboard64/COGVIDEOX_GEN_REQUEST")
    if request_file.is_file():
        prompt = request_file.read_text(encoding="utf-8").strip()

if not prompt:
    if os.path.exists("trigger_video.txt"):
        with open("trigger_video.txt", "r", encoding="utf-8") as f:
            prompt = f.read().strip()

route_chessboard64(prompt)

if not prompt:
    prompt = "一只可爱的小猫咪在阳光下的草地上打滚，高清，真实"

if not api_key:
    print("❌ 错误: 未检测到 ZHIPUAI_API_KEY！", flush=True)
    sys.exit(1)

masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
print(f"🔑 检测到 API_KEY: {masked}", flush=True)

from zhipuai import ZhipuAI
client = ZhipuAI(api_key=api_key)
print(f"🎬 准备提交任务，Prompt: {prompt}", flush=True)

task_id = None
max_submit_retries = 8
for attempt in range(1, max_submit_retries + 1):
    try:
        print(f"🔄 正在尝试提交任务 (第 {attempt}/{max_submit_retries} 次)...", flush=True)
        response = client.videos.generations(
            model="cogvideox-flash",
            prompt=prompt,
            quality="speed"
        )
        task_id = getattr(response, "id", None) or response.get("id")
        print(f"✅ 任务提交成功！Task ID: {task_id}", flush=True)
        break
    except Exception as e:
        err_msg = str(e)
        if "1305" in err_msg or "429" in err_msg or "访问量过大" in err_msg:
            print(f"⚠️ 触发智谱免费节点流控限流（1305 该模型当前访问量过大），等待 15 秒后重试提交...", flush=True)
            time.sleep(15)
        else:
            print(f"❌ 任务提交异常: {e}", flush=True)
            traceback.print_exc()
            sys.exit(1)

if not task_id:
    print("❌ 多次重试仍遇智谱云端高峰期限流(1305)，请稍后再试！", flush=True)
    sys.exit(1)

print("⏳ 正在轮询视频生成状态（约需 50~70 秒，每 8 秒查询一次）...", flush=True)
start_time = time.time()
while True:
    try:
        result = client.videos.retrieve_videos_result(id=task_id)
        status = getattr(result, "task_status", None)
        if status is None and isinstance(result, dict):
            status = result.get("task_status")
        
        elapsed = int(time.time() - start_time)
        print(f"[{elapsed}s] 当前状态: {status}", flush=True)

        if status == "SUCCESS":
            video_result = getattr(result, "video_result", None) or result.get("video_result")
            video_url = None
            if video_result and len(video_result) > 0:
                first = video_result[0]
                video_url = getattr(first, "url", None) or (first.get("url") if isinstance(first, dict) else None)
            
            print(f"\n==========================================", flush=True)
            print(f"🎉 视频生成成功！总耗时: {elapsed} 秒", flush=True)
            print(f"🔗 视频直接下载地址（30天有效）:\n{video_url}", flush=True)
            print(f"==========================================\n", flush=True)
            
            if video_url:
                print("⬇️ 正在下载视频文件保存到 output_video.mp4...", flush=True)
                res = requests.get(video_url, timeout=120)
                with open("output_video.mp4", "wb") as f:
                    f.write(res.content)
                print(f"💾 视频已保存为 output_video.mp4 (文件大小: {len(res.content)} 字节)", flush=True)
            break
        elif status == "FAIL":
            print(f"\n❌ 智谱云端渲染失败: {result}", flush=True)
            sys.exit(1)
        else:
            time.sleep(8)
    except Exception as err:
        print(f"⚠️ 查询出现异常: {err}", flush=True)
        time.sleep(8)
