"""出片工作流的自检：`.github/workflows/` 里的东西必须真的是工作流。

为什么要有这份测试：``.github/workflows/commentary-render.yml`` 需要人手动从
``production/commentary-render.workflow.yml`` 复制一次（GitHub 授权缺 ``workflows``
权限，代理写不了那个目录）。2026-09-10 那次手动复制贴进去的是**一段聊天文字**，
文件根本不是 YAML——main 上每次 push 都会产生一次 0 秒失败的 Actions 运行
（run 34421881730，GitHub 报 "workflow file issue"），而当时仓库里 39 个离线测试
全都照样通过，没有任何东西拦住它。

所以这里守四条，全部离线（不需要网络、ffmpeg、也不需要 pyyaml 才生效）：

1. ``commentary-render.yml`` 与模板**逐字节相同**——这条不需要 YAML 解析器，
   贴错内容立刻失败；
2. 每个工作流形状正确（``name`` / ``on`` / ``jobs``），且**非注释行**里不出现
   Markdown 正文特征；装了 ``pyyaml`` 时再做完整解析与结构校验；
3. 在**当前分支**上跑的工作流（没有 pin ``ref:`` 的），它引用的脚本必须在本仓库
   真实存在且能通过 ``bash -n``；pin 了 ``ref:`` 的老工作流跑的是别的分支的代码，
   脚本可以不在本分支——但必须看得出它是 pin 过的（避免"忘了 pin"混进来）。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
TEMPLATE = ROOT / "production" / "commentary-render.workflow.yml"
INSTALLED = WORKFLOWS_DIR / "commentary-render.yml"
CI_TEMPLATE = ROOT / "production" / "ci-tests.workflow.yml"
CI_INSTALLED = WORKFLOWS_DIR / "ci-tests.yml"
VERBATIM_TEMPLATE = ROOT / "production" / "verbatim-check.workflow.yml"
VERBATIM_INSTALLED = WORKFLOWS_DIR / "verbatim-check.yml"

try:  # pyyaml 不在最小依赖里：装了就做完整解析，没装就退回形状检查
    import yaml
except ImportError:  # pragma: no cover - 取决于环境
    yaml = None

# 顶层键从行首开始，值可以为空（on: / jobs:）也可以跟在冒号后（name: 解说短片出片）
TOP_LEVEL = re.compile(r"^(?P<key>[A-Za-z_][\w-]*):(?:[ \t].*)?$", re.MULTILINE)
CHECKOUT_REF = re.compile(r"^\s+ref:\s*(\S+)", re.MULTILINE)
RUNS_ON = re.compile(r"^\s*runs-on:\s*(?P<value>.+?)\s*$", re.MULTILINE)
# 仓库转私有后，GitHub-hosted 的每一分钟都在烧额度（2000 分钟/月），自托管不计分钟。
# 所以 runs-on 统一走这一个开关，见 转私有与自托管Runner手册.md。
RUNNER_SWITCH = "vars.RUNNER_LABEL"


def workflow_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))


def top_level_keys(text: str) -> set[str]:
    return set(TOP_LEVEL.findall(text))


def non_comment_lines(text: str) -> str:
    """去掉整行注释与行尾注释：模板里的 Markdown 记号都写在注释里，不算正文。"""
    kept = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        kept.append(re.sub(r"[ \t]+#.*$", "", line))
    return "\n".join(kept)


class WorkflowIntegrityTests(unittest.TestCase):
    def test_installed_workflow_is_byte_identical_to_template(self):
        """手动复制那一步贴错内容，这里必须失败。"""
        self.assertTrue(INSTALLED.exists(), f"缺少 {INSTALLED}（把模板复制过去一次）")
        self.assertEqual(
            TEMPLATE.read_bytes(), INSTALLED.read_bytes(),
            f"{INSTALLED.relative_to(ROOT)} 与模板 {TEMPLATE.relative_to(ROOT)} 不一致："
            "请重新执行 cp production/commentary-render.workflow.yml "
            ".github/workflows/commentary-render.yml",
        )

    def test_verbatim_check_template_runs_the_real_script(self):
        """逐字听检模板必须真的调用 production/verbatim_check.py，并把报告落回分支。

        这个检查的价值全在"它真的跑了"：参考片一直挂着"逐字听检没做完"，
        而 ASR 只能在 runner 上跑（沙箱连不上 Hugging Face），本地测不了。
        模板跑错脚本 == 这个洞继续挂着，还没人知道。
        """
        text = VERBATIM_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("production/verbatim_check.py", text,
                      "听检模板没有调用 production/verbatim_check.py")
        self.assertTrue((ROOT / "production" / "verbatim_check.py").exists())
        # 报告必须 commit 回分支：本环境读不到 Actions 的日志与 artifact
        self.assertIn("production/$PROJECT/delivery/verbatim-check.json", text,
                      "报告没有 commit 回分支，本地就拿不到听检结果")
        # 转写失败时也要先把报告落盘，再判失败
        self.assertIn("continue-on-error: true", text,
                      "转写不达标的运行也要先把报告 publish 出来")
        # 自托管 runner 上模型不能每跑一次重下一次：常驻缓存目录要能透传进去
        self.assertIn("WHISPER_CACHE_DIR", text,
                      "听检工作流没有透传 WHISPER_CACHE_DIR，自托管 runner 上会每次重下模型")
        # 用镜像时必须同时关掉 Xet，否则会绕过 HF_ENDPOINT 直连 cas-server.xethub.hf.co
        # 并报 "CAS Client Error: ... 401 Unauthorized"（2026-09-18 实测）
        self.assertIn("HF_HUB_DISABLE_XET", text,
                      "听检工作流没有关掉 HF 的 Xet 存储：配镜像时会 401，模型下不下来")

    def test_verbatim_workflow_matches_template_when_installed(self):
        if not VERBATIM_INSTALLED.exists():
            self.skipTest("未启用：把 production/verbatim-check.workflow.yml 复制成 "
                          ".github/workflows/verbatim-check.yml 即可")
        self.assertEqual(
            VERBATIM_TEMPLATE.read_bytes(), VERBATIM_INSTALLED.read_bytes(),
            f"{VERBATIM_INSTALLED.relative_to(ROOT)} 与模板不一致：请重新执行 "
            "cp production/verbatim-check.workflow.yml .github/workflows/verbatim-check.yml",
        )

    def test_ci_workflow_matches_template_when_installed(self):
        """CI 自检模板同样要手动复制一次；放进去了就必须与模板逐字节一致。

        没放不报错——那只是"还没启用"，不该阻断出片。但放了个改过的版本就等于
        跑的不是这份守着闸门的测试，必须拦。
        """
        if not CI_INSTALLED.exists():
            self.skipTest("未启用：把 production/ci-tests.workflow.yml 复制成 "
                          ".github/workflows/ci-tests.yml 即可（代理写不了那个目录）")
        self.assertEqual(
            CI_TEMPLATE.read_bytes(), CI_INSTALLED.read_bytes(),
            f"{CI_INSTALLED.relative_to(ROOT)} 与模板不一致：请重新执行 "
            "cp production/ci-tests.workflow.yml .github/workflows/ci-tests.yml",
        )

    def test_ci_template_actually_runs_the_offline_gate(self):
        """自检工作流不能被人改成"跑点别的"——它必须跑 production/tests。"""
        text = CI_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("production/tests", text,
                      "CI 模板没有跑 production/tests，改回去")
        self.assertIn("production/requirements.txt", text,
                      "CI 模板没有用 production/requirements.txt 装依赖")
        self.assertTrue((ROOT / "production" / "requirements.txt").exists(),
                        "CI 模板引用的 requirements.txt 不存在")
        if yaml is not None:
            jobs = yaml.safe_load(text)["jobs"]
            self.assertEqual(len(jobs), 1, "CI 只该有一个 job，别把出片混进来")
            steps = next(iter(jobs.values()))["steps"]
            self.assertTrue(any("pytest" in str(step) for step in steps),
                            "CI 里没有任何一步调用 pytest")

    def test_installed_workflow_is_yaml_not_prose(self):
        text = INSTALLED.read_text(encoding="utf-8")
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        self.assertRegex(
            first, r"^(name|on|run-name):",
            f"{INSTALLED.name} 的首个非空行是 {first!r}，看起来不是工作流（贴进聊天文字了？）",
        )
        body = non_comment_lines(text)
        self.assertNotRegex(body, r"(?m)^#{1,6}\s", "正文里有 Markdown 标题，不是 YAML 工作流")
        self.assertNotIn("**", body, "正文里有 Markdown 粗体，不是 YAML 工作流")

    def test_every_workflow_has_required_top_level_keys(self):
        files = workflow_files()
        self.assertTrue(files, "仓库里一个工作流都没有？")
        for path in files:
            with self.subTest(workflow=path.name):
                keys = top_level_keys(path.read_text(encoding="utf-8"))
                for required in ("name", "jobs"):
                    self.assertIn(required, keys, f"{path.name} 缺顶层 {required}:")
                self.assertTrue(
                    {"on", "true"} & keys,
                    f"{path.name} 缺触发器 on:（pyyaml 把 on 解析成布尔 True，故两者都认）",
                )

    @unittest.skipIf(yaml is None, "未安装 pyyaml，跳过完整解析")
    def test_every_workflow_parses_and_declares_a_runnable_job(self):
        files = workflow_files() + sorted(ROOT.glob("production/**/*.workflow.yml"))
        for path in files:
            with self.subTest(workflow=path.name):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict, f"{path.name} 顶层不是映射")
                trigger = data.get("on", data.get(True))
                self.assertIsNotNone(trigger, f"{path.name} 没有触发器")
                jobs = data["jobs"]
                self.assertIsInstance(jobs, dict, f"{path.name} 的 jobs 不是映射")
                for job_name, job in jobs.items():
                    self.assertIn("runs-on", job, f"{path.name}:{job_name} 缺 runs-on")
                    self.assertIn("steps", job, f"{path.name}:{job_name} 缺 steps")

    def test_no_workflow_hardcodes_a_github_hosted_runner(self):
        """runs-on 必须走仓库变量开关，不能写死 ubuntu-latest。

        仓库一旦转私有，GitHub-hosted 的每分钟都从 2000 分钟额度里扣；自托管 runner 不计分。
        写死 ``ubuntu-latest`` 的话，切 runner 那天会漏掉这个工作流，继续偷偷烧额度
        ——而且因为不报错，没人会发现。开关的形状只有一种：
        ``runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}``，
        没设变量时行为与切私有之前一模一样。
        """
        files = workflow_files() + sorted(ROOT.glob("production/**/*.workflow.yml"))
        self.assertTrue(files, "仓库里一个工作流都没有？")
        for path in files:
            text = path.read_text(encoding="utf-8")
            values = RUNS_ON.findall(text)
            with self.subTest(workflow=path.name):
                self.assertTrue(values, f"{path.name} 里一个 runs-on 都没有")
                for value in values:
                    self.assertIn(
                        RUNNER_SWITCH, value,
                        f"{path.name} 的 runs-on 写死了 {value!r}：转私有后这里会继续烧 "
                        "GitHub-hosted 额度。改成 "
                        "${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}",
                    )

    def test_render_workflow_inputs_match_run_project_script(self):
        """工作流填的 slug 必须能喂给 run_project.sh，路径不能对不上。"""
        text = INSTALLED.read_text(encoding="utf-8")
        self.assertIn("production/run_project.sh", text,
                      "出片工作流没有调用共用的 production/run_project.sh")
        self.assertTrue((ROOT / "production" / "run_project.sh").exists())
        if yaml is None:
            return
        inputs = yaml.safe_load(text)[True]["workflow_dispatch"]["inputs"]
        self.assertIn("project", inputs, "缺 project 输入（Actions 里要填 slug）")

    def test_film_name_input_reaches_run_project_script(self):
        """成片名要能从 Actions 一路传到 run_project.sh 的第 3 个参数。

        不传的话脚本会用 story.json 的标题当文件名，对已经交付过的片子就会在
        交付/ 里多出一个 48 MB 的副本（dahlia 的成片名是"黑色大丽花_三分钟_带声音"，
        跟标题不是一回事）。
        """
        text = INSTALLED.read_text(encoding="utf-8")
        self.assertIn("inputs.film_name", text, "工作流没有暴露 film_name 输入")
        self.assertRegex(text, r'run_project\.sh\s+"\$PROJECT"\s+"\$SKIP_ASR"\s+"\$FILM_NAME"',
                         "工作流没有把成片名作为第 3 个参数传给 run_project.sh")
        script = (ROOT / "production" / "run_project.sh").read_text(encoding="utf-8")
        self.assertRegex(script, r'FILM="[^"]*\$\{3:-',
                         "run_project.sh 的第 3 个参数没有回退到默认片名")
        # 直接把脚本里那行 FILM=... 拿出来执行：空片名要退回标题，给了片名要用给的
        film_line = re.search(r"(?m)^FILM=.*$", script)
        self.assertIsNotNone(film_line, "run_project.sh 里找不到 FILM= 赋值行")
        harness = f'set -euo pipefail; WORK=work/p; SAFE_TITLE="默认标题"; {film_line.group(0)}; printf %s "$FILM"'
        for args, expected in ((("p", "false", ""), "work/p/默认标题.mp4"),
                               (("p", "false", "原名.mp4"), "work/p/原名.mp4")):
            with self.subTest(argv=args):
                proc = subprocess.run(["bash", "-c", harness, "bash", *args],
                                      cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout, expected)
        # 位置参数契约：少了 slug 必须报错退出，不能默默按空项目跑下去
        proc = subprocess.run(["bash", "production/run_project.sh"], cwd=ROOT,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, "缺 slug 时应当以非 0 退出")
        proc = subprocess.run(["bash", "production/run_project.sh", "no-such-project"],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("没有这个项目", proc.stdout + proc.stderr)

    def test_render_push_is_retried(self):
        """成片的最后一次 git push 必须重试。

        为什么：出片要跑几十到 90 分钟，成片与实测报告全靠最后这一次 push 回到分支。
        2026-09-18 在自托管 runner 上实测到 git 连 github.com 偶发 133 秒超时
        （日志原文 "133182 ms: Connection timed out"，actions/checkout 内置的 3 次
        重试都没扛住），而当时的脚本只推一次——等于把整场渲染的成果交给运气。
        """
        script = (ROOT / "production" / "run_project.sh").read_text(encoding="utf-8")
        push_at = script.index('push origin "HEAD:$BRANCH"')
        self.assertRegex(script[:push_at][-1200:], r"for attempt in",
                         "推送没有被重试循环包住：网络抖一次就前功尽弃")
        self.assertIn("push_ok", script, "推送失败没有被检查，失败了也不知道")
        self.assertIn("exit 1", script[push_at:][:1200],
                      "全部重试都失败时必须非 0 退出，不能假装成功")

    def test_render_push_fails_fast_and_retries_many_times(self):
        """推送要「快失败、多试」，不能「少试、慢失败」。

        2026-09-20 在自托管 runner 上实测：脚本原来的写法是 5 次重试，但每一轮
        git push 自己要卡满 300 秒才报错
        （"Failed to connect to github.com port 443 after 299980 ms: Connection timed out"），
        5 × (300 + 20) 秒 ≈ 25 分钟全用来等同一个连不上的 socket；于是一次渲染 180 秒、
        音频三道闸门全过、成片也 add/commit 好了的出片被判成失败。
        而同一分钟里 `curl https://github.com` 返回 200 / 2.2 秒 —— 链路是通的，
        只是那几次连接不走运。
        所以：先用 TCP 探针确认端口可达（不可达就跳过本轮，别把 300 秒交给 git 的
        connect 超时），再给传输加低速放弃阈值，并把轮数从 5 提到 40。
        """
        script = (ROOT / "production" / "run_project.sh").read_text(encoding="utf-8")
        push_at = script.index('push origin "HEAD:$BRANCH"')
        around = script[max(0, push_at - 1200): push_at + 1200]
        self.assertIn("/dev/tcp/github.com/443", around,
                      "推送前没有 TCP 探针，不可达时每轮仍要白等 git 自己的超时")
        self.assertIn("timeout 4", around, "TCP 探针没有超时上限")
        self.assertIn("lowSpeedLimit=1000", around,
                      "没有低速放弃阈值，卡住的传输会一直占着这一轮")
        self.assertIn("lowSpeedTime=30", around, "低速阈值没有时间上限")
        self.assertRegex(around, r"seq 1 (?:[3-9]\d|\d{3,})",
                         "重试轮数太少：单轮快失败才有意义多试，至少要 30 轮")
        self.assertIn("sleep 15", around, "重试间隔应短（15 秒级），长间隔又变成慢失败")

    def test_run_project_disables_a_stale_sparse_checkout(self):
        """提交成片前必须先把上一个 job 留在 _work 目录里的 sparse-checkout 关掉。

        2026-09-20 实测：离线自检（ci-tests）用 sparse-checkout 跳过 *.mp4 省 48 MB，
        它把 core.sparseCheckout 留在同一个 _work 目录的 .git/config 里；出片的三道闸门
        （1080p / 180s / 音频）全过，却倒在第 4/5 步 commit——成片 add 不进索引，
        一次成功的出片被 workflow 判成失败。所以 run_project.sh 必须先关掉这个残留，
        而且必须出现在 `git add 成片` 之前。
        """
        script = (ROOT / "production" / "run_project.sh").read_text(encoding="utf-8")
        self.assertIn("core.sparseCheckout false", script,
                      "run_project.sh 没有把残留的 sparse-checkout 关掉")
        self.assertLess(
            script.index("core.sparseCheckout false"),
            script.index('git add -f "交付/'),
            "关掉 sparse-checkout 必须发生在 git add 成片之前，否则成片还是进不了索引",
        )
        # 兜底要能对上 ci-tests 那边留下来的 sparse-checkout 形状（跳过 *.mp4）
        ci = CI_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("!*.mp4", ci,
                      "离线自检模板不再用 sparse-checkout 跳过 *.mp4 了？上面的兜底要同步改")

    def test_artifact_cleanup_workflow_can_actually_delete(self):
        """清理工作流必须声明 actions: write —— 没有它删除会 403，配额照样满。

        2026-09-18：仓库积了 3.1 GB artifact（免费额度 500 MB），出片最后一步报
        "Artifact storage quota has been hit"。代理自己的令牌没有 actions 权限
        （实测 DELETE 403），但工作流自带的 GITHUB_TOKEN 只要在 permissions 里声明
        actions: write 就能删。
        """
        path = WORKFLOWS_DIR / "cleanup-artifacts.yml"
        self.assertTrue(path.exists(), "缺少 artifact 清理工作流")
        text = path.read_text(encoding="utf-8")
        self.assertIn("actions: write", text, "没声明 actions: write，删除会 403")
        self.assertIn("workflow_dispatch", text, "清理工作流要能手动触发")
        # 上传那一步不能因为配额满就把整场出片判死
        render = INSTALLED.read_text(encoding="utf-8")
        upload_at = render.index("actions/upload-artifact")
        self.assertIn("continue-on-error: true", render[:upload_at][-400:],
                      "成片上传失败会把出片判死，但成片本来就 commit 回 交付/ 了")

    def test_scripts_run_on_this_branch_exist_and_are_valid_shell(self):
        """只有没 pin ref 的工作流跑本分支代码，它们引用的脚本必须真的在这儿。"""
        checked = pinned = 0
        for path in workflow_files():
            text = path.read_text(encoding="utf-8")
            scripts = re.findall(r"bash\s+(production/[\w./-]+\.sh)", text)
            refs = CHECKOUT_REF.findall(text)
            if refs:
                pinned += len(scripts)
                self.assertTrue(
                    all(not ref.startswith(("refs/", "$")) for ref in refs),
                    f"{path.name} 的 ref 是动态表达式，无法判断它跑哪个分支",
                )
                continue  # 老工作流：跑的是别的分支上的脚本，本分支没有是正常的
            for script in scripts:
                with self.subTest(workflow=path.name, script=script):
                    target = ROOT / script
                    self.assertTrue(target.exists(),
                                    f"{path.name} 在当前分支上调用了不存在的 {script}")
                    proc = subprocess.run(["bash", "-n", str(target)],
                                          capture_output=True, text=True)
                    self.assertEqual(proc.returncode, 0, f"{script} 语法错误：{proc.stderr}")
                    checked += 1
        self.assertGreaterEqual(checked, 1,
                                "没有任何在当前分支上运行的脚本被检查到，正则失配了")
        self.assertGreaterEqual(pinned, 1, "应当存在 pin 了 ref 的历史工作流")


if __name__ == "__main__":
    unittest.main()
