"""本地 runner 三件套的自检（离线，不联网、不需要 ffmpeg）。

为什么要有这份测试：``runner/`` 里的三个脚本是**在仓库主的私人机器上以 sudo 跑**的，
装错一步（漏了中文字体、把 token 打进日志、在公开仓库上注册）代价都比 CI 红一次大。
它们不会被任何工作流调用，所以 ``test_workflows.py`` 那套"工作流引用的脚本"检查
覆盖不到——这里单独守四条：

1. 三个脚本都得是语法正确的 bash（``bash -n``）；
2. 默认仓库、开关变量名必须和工作流里的对得上（``RUNNER_LABEL`` / ``WHISPER_CACHE_DIR``）；
3. ``setup-runner.sh`` 必须先查仓库可见性、**公开就拒绝注册**，并且提供的退路是
   ``--no-register``（公开仓库上挂自托管 runner = 任何 fork PR 都能在那台机器上执行代码）；
4. token 只现场取、不落盘、不进输出（脚本里不能出现会把它打印出来的写法）。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER_DIR = ROOT / "runner"
SETUP = RUNNER_DIR / "setup-runner.sh"
SELFCHECK = RUNNER_DIR / "selfcheck.sh"
UNINSTALL = RUNNER_DIR / "uninstall-runner.sh"
WATCHDOG = RUNNER_DIR / "watchdog.sh"
README = RUNNER_DIR / "README.md"
MANUAL = ROOT / "转私有与自托管Runner手册.md"

# 与 .github/workflows/*.yml 里 runs-on 用的开关是同一个
EXPECTED_REPO = "32r4e2q-hub/desktop-tutorial"
ECHO_TOKEN = re.compile(r"echo[^#\n]*\$\{?TOKEN\}?", re.IGNORECASE)


class RunnerScriptTests(unittest.TestCase):
    def test_all_three_scripts_exist_and_are_valid_shell(self):
        for script in (SETUP, SELFCHECK, UNINSTALL):
            with self.subTest(script=script.name):
                self.assertTrue(script.exists(), f"缺 {script}")
                proc = subprocess.run(["bash", "-n", str(script)],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0,
                                 f"{script.name} 语法错误：{proc.stderr}")

    def test_readme_exists_and_points_at_the_manual(self):
        self.assertTrue(README.exists(), "runner/README.md 是给仓库主看的最短路径，不能没有")
        text = README.read_text(encoding="utf-8")
        self.assertIn("转私有与自托管Runner手册.md", text,
                      "runner/README.md 要指回完整手册，别让人只看三分钟版就去动仓库设置")
        self.assertTrue(MANUAL.exists())

    def test_scripts_default_to_this_repository(self):
        for script in (SETUP, SELFCHECK, UNINSTALL):
            with self.subTest(script=script.name):
                self.assertIn(EXPECTED_REPO, script.read_text(encoding="utf-8"),
                              f"{script.name} 的默认仓库不是本仓库")

    def test_switch_names_match_the_workflows(self):
        """脚本设的变量名，必须就是工作流读的那几个。"""
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("RUNNER_LABEL", setup)
        self.assertIn("WHISPER_CACHE_DIR", setup)
        # 走镜像时必须一起关掉 Xet，否则 HF 会绕过 HF_ENDPOINT 直连 cas-server 被 401
        self.assertIn("HF_HUB_DISABLE_XET", setup)

    def test_setup_refuses_to_register_on_a_public_repository(self):
        """公开仓库上挂自托管 runner，等于把机器交给任何 fork PR。"""
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn(".private", setup, "注册前必须先查仓库可见性")
        self.assertIn("--no-register", setup, "仓库还是公开时，要给一条只装软件不注册的退路")
        index = setup.index("--no-register")
        self.assertLess(index, setup.index("./config.sh"),
                        "拒绝注册的分支要出现在真正调用 config.sh 之前")

    def test_token_is_never_printed_or_written_to_disk(self):
        """token 只现场取、用完 unset；脚本里不能有 echo $TOKEN 之类的写法。"""
        for script in (SETUP, UNINSTALL):
            with self.subTest(script=script.name):
                text = script.read_text(encoding="utf-8")
                self.assertIsNone(ECHO_TOKEN.search(text),
                                  f"{script.name} 会把 token 打印出来")
                self.assertIn("unset TOKEN", text,
                              f"{script.name} 用完 token 要 unset")

    def test_selfcheck_fails_loudly_when_a_hard_requirement_is_missing(self):
        """自检遇到必须修的问题（缺 ffmpeg / 没字体）要返回非 0，别让人以为能出片。"""
        text = SELFCHECK.read_text(encoding="utf-8")
        self.assertIn("exit 1", text)
        self.assertIn("fonts-noto-cjk", text, "中文字体缺失要给出那条 apt 命令")
        self.assertIn("repos/$REPO", text, "自检要顺手确认仓库仍是私有")

    def test_setup_blocks_musl_and_explains_why(self):
        """Alpine / musl 要直接拦下，别让它装到一半才撞墙。

        `wsl` 默认丢出来的可能是 Alpine：GitHub 官方 runner 只发 glibc 构建，
        出片脚本还写死了 sudo apt-get install fonts-noto-cjk，musl 系根本跑不通。
        """
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("musl", setup, "必须探测 musl libc")
        self.assertIn("glibc", setup, "拦下的时候要说明原因（runner 只有 glibc 构建）")
        # 拦截动作里要给出换回 Ubuntu / Debian 系的退路，而不是一句干巴巴的拒绝
        self.assertRegex(setup, r"Ubuntu\s*/\s*Debian", "拦下 musl 时要给出换发行版的退路")

    def test_setup_installs_cjk_fonts_independently_of_other_deps(self):
        """中文字体要单独查、单独装，不能跟着 '依赖都在就整段跳过' 一起被跳过。

        2026-09-20 实测：ffmpeg 等都在时，脚本整段跳过 apt，中文字体就从没被装过，
        出片才在 render 那步报 'refusing to render missing glyphs'。
        """
        setup = SETUP.read_text(encoding="utf-8")
        # 第二次检查必须脱离第一次装依赖的 apt 分支（ffmpeg / python 都在的时候也要查 font）
        idx = setup.index("fc-list | grep -qi")
        # 字体装的是 fonts-noto-cjk，而且是独立的一条安装
        self.assertIn("fonts-noto-cjk", setup[idx:],
                      "字体检查后面没有独立的一条 fonts-noto-cjk 安装")
        # 有 apt-get 时才自动补装；没有（非 apt 发行版）得警告，不能让它默默过去
        self.assertTrue(
            ("apt-get install" in setup[idx:] and "refusing to render missing glyphs" in setup),
            "字体缺失时要么 apt-get 补装，要么给出 refusing-to-render 的警告",
        )

    def test_setup_removes_a_stale_registration_before_configuring(self):
        """目录里已有 .runner 时，注册前要先用 config.sh remove 摘掉旧注册。

        2026-09-20 实测：旧注册挡路时 config.sh 报 'already configured'，
        --replace 在部分版本上不顶用；先 remove 再注册才真的幂等。
        """
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("config.sh remove", setup, "注册前要先用 config.sh remove 摘掉旧注册")
        remove_idx = setup.index("config.sh remove")
        # remove 拿到的也是同一个现场 token
        self.assertIn("--token", setup[remove_idx:remove_idx + 120],
                      "remove 也要带现场取到的 token")
        remove_line = next(ln for ln in setup.splitlines() if "config.sh remove" in ln)
        self.assertIn('"$TOKEN"', remove_line, "remove 要用同一个 $TOKEN，别拼第二把")
        # remove 要发生在真正的注册（--url）之前，顺序不能反
        self.assertLess(remove_idx, setup.index("./config.sh --url"),
                        "先摘旧注册、再注册，顺序反了等于白摘")

    def test_setup_checks_online_status_without_gh_api_arg(self):
        """gh api 没有 --arg 参数：写 `--jq --arg n "$RUNNER_NAME"` 每次查询都失败、白等。

        名字必须拼进 --jq 表达式（select(.name==…)，双引号包住），而不是当参数传。
        """
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("--arg", setup, "注释里要留下这个坑，别让后人再写回去")
        for ln in setup.splitlines():
            if ln.lstrip().startswith("#"):
                continue
            if "gh api" in ln and "--arg" in ln:
                self.fail(f"gh api 调用里不能带 --arg：{ln!r}")
        # 名字拼进 --jq：先 assign 一个带 select(.name==…) 的表达式，再 --jq 引用它
        self.assertIn("select(.name==", setup, "名字要拼进 --jq 的 select(.name==…)")
        self.assertIn('--jq "$RJQ"', setup, "查询要引用拼好的 jq 表达式")

    def test_setup_sets_pypi_mirror_even_without_a_pip3_command(self):
        """--pypi-mirror 在只有 python3 -m pip 的机器上会静默失败（pip3 命令不存在），
        必须退回 python3 -m pip 再试，而不是一声不吭地装成成功。"""
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("python3 -m pip config", setup,
                      "pip3 不存在时要退回 python3 -m pip config 设镜像")
        self.assertIn("PYPI_MIRROR", setup)

    def test_setup_keeps_the_background_runner_alive_via_setsid_disown(self):
        """后台 runner 必须 setsid + disown 活着，且判据不能是假阳性。

        2026-09-20 实测：`a || b &` 的 & 作用于整个 || 列表，且缺 setsid 时脚本一退出
        进程就没了；而 pgrep -f 'Runner.Listener' 会命中后台子进程命令行的同名字样，
        属于假阳性（runner 其实死了还在说"已在后台跑"）。
        """
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("setsid ./run.sh", setup, "后台启动必须走 setsid")
        self.assertIn("disown", setup, "setsid 起的进程还要 disown，才不会被 shell 拖走")
        # 判据要看监听器可执行文件本身（bin/Runner.Listener），两条都不行：
        #   * 裸的 Runner.Listener —— 任何提到这个名字的进程都算命中（假阳性）；
        #   * run.sh —— 它已经把自己 exec 成了监听器，机器上根本找不到这个名字（假阴性）。
        haystack = setup[setup.index("setsid ./run.sh"):]
        self.assertNotIn("pgrep -f \"Runner.Listener\"", haystack,
                         "后台存活的判据不能再用裸的 Runner.Listener（假阳性）")
        self.assertIn(r"bin/Runner\.Listener", haystack,
                      "存活判据要认准监听器可执行文件路径")
    def test_watchdog_script_exists_and_is_valid_shell(self):
        """看门狗要和另外三个脚本一样是合法 bash，并且能独立运行（--help 之外不该炸）。"""
        self.assertTrue(WATCHDOG.exists(),
                        "缺 runner/watchdog.sh：没有 systemd 的后台 runner 会静默死掉，没人拉它")
        proc = subprocess.run(["bash", "-n", str(WATCHDOG)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"watchdog.sh 语法错误：{proc.stderr}")

    def test_watchdog_does_not_match_itself_or_other_mere_mentions(self):
        """存活判断必须认准 bin/Runner.Listener，不能用裸的 Runner.Listener。

        ``pgrep -f`` 比的是整条命令行，任何**提到**这个名字的进程都算命中：
        ``grep Runner.Listener``、包着看门狗的外层脚本、甚至看门狗自己的测试壳。
        一旦误判成「还活着」，看门狗就什么都不做 —— 而它存在的唯一意义就是别误判。
        真实进程的命令行一定含 bin/Runner.Listener（run.sh 里就是 ./bin/Runner.Listener run）。
        """
        text = WATCHDOG.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn(r"bin/Runner\.Listener", code, "存活判断没有认准监听器可执行文件路径")
        self.assertNotIn("pgrep -f 'Runner.Listener'", code,
                         "裸的 Runner.Listener 会被任何提到它的进程命中，导致看门狗永远不干活")
        self.assertIn("pgrep -f \"$RUNNER_PATTERN\"", code, "存活判断要复用同一个模式变量")

    def test_watchdog_detaches_the_runner_and_releases_the_lock(self):
        """拉起监听器要 setsid（否则看门狗一退它就被带走），并且不能把 flock 的 fd 传下去。

        实测踩过：flock 用的 fd 被 ``setsid ... &`` 继承，runner 活得越久锁被攥得越久，
        之后每次看门狗都以为「上一次还在跑」而跳过 —— 看门狗自己把自己锁死了。
        """
        text = WATCHDOG.read_text(encoding="utf-8")
        self.assertIn("setsid nohup ./run.sh", text)
        self.assertIn("9>&-", text, "没有把 flock 的 fd 关掉，锁会被 runner 一直攥着")
        self.assertIn("flock -n", text, "没有防重入：两次检查叠在一起会拉起两个监听器")

    def test_watchdog_does_not_log_on_every_check(self):
        """每次检查都写一行日志的话，一天 288 行会把真正的事故记录淹掉。

        正常检查只更新心跳文件（.watchdog-heartbeat），只有真的动手了才写 watchdog.log。
        """
        text = WATCHDOG.read_text(encoding="utf-8")
        self.assertIn(".watchdog-heartbeat", text, "没有心跳文件，事后无法确认看门狗还在跑")
        verbose_line = [ln for ln in text.splitlines()
                        if "runner 活着，不动它" in ln and ln.lstrip().startswith("[")]
        self.assertTrue(verbose_line, "「活着」的分支不该无条件写日志，要藏在 WATCHDOG_VERBOSE 后面")
        # 「还活着」这条路径上不许有无条件写日志的语句（日志只在真的动手之后才有）
        slice_ = text[text.index("RUNNER_PATTERN="):text.index('log "runner 不在了')]
        unconditional = [ln for ln in slice_.splitlines() if ln.strip().startswith("log ")]
        self.assertEqual(unconditional, [],
                         f"检查还活着的时候就写日志了：{unconditional}")

    def test_watchdog_functionally_restarts_a_dead_listener(self):
        """离线跑一遍真的看门狗：没注册不动、注册了没进程要拉起、已在跑要静默、掉线要拉回。"""
        import os
        import shutil
        import tempfile
        import time

        sleep_bin = shutil.which("sleep")
        if not sleep_bin:
            self.skipTest("这个系统没有 sleep，跑不了功能测试")
        pattern = r"bin/Runner\.Listener"
        # 这个测试会 pkill 所有匹配 bin/Runner.Listener 的进程。在 GitHub Actions 的 runner 上，
        # 正在执行本作业的监听器就叫这个名字 —— 杀掉它等于把「离线自检」自己掐死
        # （表现为 "Run the offline gate" 步骤 cancelled、整次运行 failure，2026-09-21 在
        # arena/01a0c30d 分支上连续五次复现）。所以只在本机跑，Actions 上跳过。
        if os.environ.get("GITHUB_ACTIONS") == "true" or subprocess.run(
                ["pgrep", "-f", pattern], capture_output=True, text=True).stdout.strip():
            self.skipTest("检测到真实的 Runner.Listener 或 GITHUB_ACTIONS 环境：pkill 会杀掉正在跑本作业的 runner")

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "bin").mkdir()
            shutil.copy(sleep_bin, home / "bin" / "Runner.Listener")
            (home / "run.sh").write_text(
                '#!/bin/bash\nexec "$(dirname "$0")/bin/Runner.Listener" 600\n', encoding="utf-8")
            (home / "run.sh").chmod(0o755)
            env = {**os.environ, "RUNNER_DIR": str(home), "WATCHDOG_WAIT": "6"}

            def listener_count():
                out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
                return len([x for x in out.stdout.split() if x])

            def run_watchdog():
                return subprocess.run(["bash", str(WATCHDOG)], capture_output=True, text=True, env=env)

            def kill_listeners():
                subprocess.run(["pkill", "-f", pattern], capture_output=True)
                time.sleep(0.4)

            kill_listeners()
            try:
                # ① 没注册：明确说不做，非 0 退出
                proc = run_watchdog()
                self.assertNotEqual(proc.returncode, 0, "没注册还返回 0，会让人以为保活已经生效")
                self.assertIn("还没注册", proc.stdout)
                self.assertEqual(listener_count(), 0, "没注册居然还去拉进程")

                # ② 注册了、没有监听器：拉起
                (home / ".runner").touch()
                proc = run_watchdog()
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn("已重新上线", proc.stdout)
                self.assertEqual(listener_count(), 1, "看门狗说拉起来了，实际没有进程")

                # ③ 已经在跑：静默退出，日志不增行
                before = len((home / "watchdog.log").read_text(encoding="utf-8").splitlines())
                proc = run_watchdog()
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout.strip(), "", "还活着就不该刷屏")
                after = len((home / "watchdog.log").read_text(encoding="utf-8").splitlines())
                self.assertEqual(after, before, "每次检查都写日志，会把事故记录淹掉")

                # ④ 监听器被杀：重新拉起（这才是它存在的理由）
                kill_listeners()
                self.assertEqual(listener_count(), 0)
                proc = run_watchdog()
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertEqual(listener_count(), 1, "掉线之后没拉回来")
            finally:
                kill_listeners()

    def test_setup_installs_the_watchdog(self):
        """setup-runner.sh 在没有 systemd 的分支里必须顺手把看门狗装上。

        否则每台新机器都要人工记得挂一次计划任务 —— 而忘掉它的代价就是
        「任务卡在 Waiting for a runner 一整天」这种最难排查的故障。
        """
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("install_watchdog()", setup, "setup-runner.sh 里没有装看门狗的函数")
        self.assertIn("install_watchdog\n", setup, "定义归定义，没有在装服务那一步调用它")
        self.assertIn("runner-watchdog", setup, "计划任务名要固定，重复安装才能覆盖成同一个")
        self.assertIn("wsl.exe -d", setup, "计划任务要通过 wsl.exe 进到这台发行版里执行")
        self.assertIn("schtasks", setup)
        # 它得在「没有 systemd → 退回后台进程」的分支里被调用
        background = setup.index("没有 systemd")
        self.assertLess(background, setup.rindex("install_watchdog\n"),
                        "看门狗只在 systemd 拿不到、退回后台进程时才需要")

    def test_setup_watchdog_install_is_idempotent_and_reports_failure(self):
        """装看门狗要幂等（/f 覆盖同一个任务），并且失败时给出可复制的手动命令。"""
        setup = SETUP.read_text(encoding="utf-8")
        self.assertIn("/f", setup, "计划任务没有 /f，第二次安装会因为重名而失败")
        self.assertIn("SCHTASKS", setup, "schtasks 路径要能覆盖，否则没法离线测试")
        self.assertIn("计划任务没建成", setup, "计划任务建失败必须明说并给出替代命令")

    def test_setup_judges_the_listener_not_the_wrapper_shell(self):
        """setup 判断"后台跑起来了没"要盯 bin/Runner.Listener，不能盯 run.sh。

        2026-09-20 在真机上对比过：`pgrep -af 'bin/Runner\\.Listener'` 报的是
        `/home/runner/actions-runner/bin/Runner.Listener run` —— run.sh 已经把
        自己 exec 掉、命令行就是监听器本身，所以
          * 盯 `run\\.sh`：机器上正常运行的那个进程根本不带这个名字 → 判成"没起来"
            → 重复启动 → `A session for this runner already exists`；
          * 盯裸的 `Runner.Listener`：任何提到这个名字的进程都算命中（假阳性）。
        唯一可靠的判据是监听器可执行文件的路径。看门狗（watchdog.sh）用同一个判据，
        两边必须一致，否则 setup 说"没起来"、看门狗说"还活着"。
        """
        setup = SETUP.read_text(encoding="utf-8")
        watchdog = WATCHDOG.read_text(encoding="utf-8")
        self.assertIn(r"bin/Runner\.Listener", setup, "setup 的存活判据没有认准监听器路径")
        self.assertIn(r"bin/Runner\.Listener", watchdog, "看门狗的存活判据没有认准监听器路径")
        code = "\n".join(line for line in setup.splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertNotIn('(^|[ /])run\\.sh( |$)', code,
                         "run.sh 已经被 exec 掉，盯它会把正常运行的 runner 判成'没起来'")
        self.assertNotIn("pgrep -f \"Runner.Listener\"", code,
                         "裸的 Runner.Listener 会被任何提到它的进程命中（假阳性）")



if __name__ == "__main__":
    unittest.main()
