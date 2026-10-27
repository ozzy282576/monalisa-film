"""脚手架测试（狂犬病模式）：新题目目录能不能被真实地用起来。

覆盖四件事：
1. 复制出来的引擎副本、渲染模板、工作流里没有残留参考项目的路径 / 分支 / 片名 / 案件内容；
2. 生成的 ``story.json`` 骨架在时间轴上是机械正确的（45 镜 × 4 秒、6 章 × 30 秒），
   ``generate.validate()`` 在提示词为空时**会拦下来**、填完之后**放行**；
3. 模板 ``render.py`` 的关键守卫真的在：CUTS 骨架覆盖全部镜头、每镜只用一次（复用会被 make_edl 拒绝）、
   信息卡 / 片尾卡从 ``story.json`` 的 ``presentation`` 取文案（缺文案就报错）；
   模板 ``build_story.py`` 能写出带 ``presentation`` 的 story.json，``--publish`` 不依赖配音就能出发布文案；
4. 参考项目 ``production/rabies1885`` 在脚手架运行前后一个字节都没变。
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))
import agnes_video  # noqa: E402  (共用引擎：空提示词由它先拦下)
import new_topic  # noqa: E402

SLUG = "scaffoldtest"
TITLE = "测试题目：脚手架自检"
BRANCH = "arena/scaffold-test-branch"
REFERENCE = ROOT / "production/rabies1885"
RUNS_ON = "runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _hash_tree(root: Path) -> dict:
    import hashlib
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


class ScaffoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference_before = _hash_tree(REFERENCE)
        cls.tmp = Path(tempfile.mkdtemp(prefix="scaffold-test-"))
        # 副本里的 generate.py 会按 parents[2] 找仓库根，再把 ROOT/production
        # 放进 sys.path 去找共享引擎 agnes_video.py，所以临时目录要长成仓库的样子。
        cls.production = cls.tmp / "production"
        cls.production.mkdir(parents=True)
        shutil.copy2(ROOT / "production/agnes_video.py", cls.production / "agnes_video.py")
        if (ROOT / ".cache/fonts").is_dir():   # 本机渲染信息卡用的 CJK 字体（render.find_font 先查 ROOT/.cache/fonts）
            shutil.copytree(ROOT / ".cache/fonts", cls.tmp / ".cache/fonts")
        cls.project_dir = cls.production / SLUG
        new_topic.scaffold(SLUG, TITLE, BRANCH, cls.project_dir, REFERENCE)
        cls.workflows = {
            kind: cls.project_dir / "workflows" / f"{SLUG}-{kind}.yml"
            for kind in ("gen", "render", "verbatim", "visual-qc")
        }

    @classmethod
    def tearDownClass(cls):
        for name in list(sys.modules):
            if name.startswith("scaffold_"):
                del sys.modules[name]
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # -- 1. 副本干净 ------------------------------------------------------
    def test_engine_template_and_workflow_files_present(self):
        for name in (*new_topic.ENGINE_FILES, *new_topic.TEMPLATE_FILES):
            self.assertTrue((self.project_dir / name).is_file(), name)
        for name in ("story.json", "screenplay.md", "README.md", "audio/manifest.json"):
            self.assertTrue((self.project_dir / name).is_file(), name)
        for path in self.workflows.values():
            self.assertTrue(path.is_file(), path.name)
        self.assertTrue((self.project_dir / "audio/raw").is_dir())

    def test_no_reference_identity_leaks_into_the_copy(self):
        leftovers = []
        # 只扫"复制出来的副本"：.py / .yml。story.json、README.md、screenplay.md 是新生成的文档，
        # 里面**故意**保留"参考 production/rabies1885"的出处说明；build_story.py 的文档字符串也允许
        # 提一次样板出处，但案情内容、分支、成片名一个都不许出现。
        forbidden = ("work/rabies1885", new_topic.REFERENCE_BRANCH, "cb25986c", new_topic.REFERENCE_FILM,
                     "狂犬病疫苗", "巴斯德", "迈斯特", "pasteur", "rabies1885-agnes", "rabies1885-render",
                     "rabies1885-verbatim", "rabies1885-visual-qc", "'rabies1885: '")
        for path in sorted(self.project_dir.rglob("*")):
            if not path.is_file() or path.suffix not in (".py", ".yml"):
                continue
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            for token in forbidden:
                if token.lower() in lowered:
                    leftovers.append(f"{path.name}:{token}")
            if path.name != "build_story.py" and "rabies1885" in lowered:
                leftovers.append(f"{path.name}:rabies1885")
        self.assertEqual(leftovers, [])
        story = json.loads((self.project_dir / "story.json").read_text())
        self.assertEqual(story["_scaffold"]["reference"], "production/rabies1885")
        self.assertEqual(story["presentation"], {})

    def test_branch_and_artifact_names_follow_the_new_project(self):
        generator = load_module("scaffold_generate", self.project_dir / "generate.py")
        self.assertEqual(generator.BRANCH, BRANCH)
        story = json.loads((self.project_dir / "story.json").read_text())
        self.assertEqual(story["branch"], BRANCH)
        self.assertEqual(story["title"], TITLE)
        film = new_topic.film_name(TITLE)
        self.assertEqual(film, "测试题目_脚手架自检_三分钟_带声音.mp4")
        for kind, path in self.workflows.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"refs/heads/{BRANCH}", text, kind)
            self.assertIn(f"production/{SLUG}/", text, kind)
            self.assertNotIn("rabies1885", text.lower(), kind)
        gen = self.workflows["gen"].read_text(encoding="utf-8")
        self.assertIn(f"production/{SLUG}/GEN_REQUEST", gen)
        self.assertIn(f"python3 production/{SLUG}/generate.py --validate", gen)
        render = self.workflows["render"].read_text(encoding="utf-8")
        self.assertIn(f"production/{SLUG}/RENDER_REQUEST", render)
        self.assertIn(film, render)
        # 出片步骤统一在共用脚本里，工作流只是薄薄一层
        self.assertIn("bash production/run_project.sh", render)
        verbatim = self.workflows["verbatim"].read_text(encoding="utf-8")
        self.assertIn(f"production/{SLUG}/VERBATIM_REQUEST", verbatim)
        visual_qc = self.workflows["visual-qc"].read_text(encoding="utf-8")
        self.assertIn(f"production/{SLUG}/VISUAL_QC_REQUEST", visual_qc)
        self.assertIn(f"production/{SLUG}/audit_frame_distortions.py", visual_qc)

    def test_workflows_parse_and_follow_repo_conventions(self):
        for kind, path in self.workflows.items():
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsInstance(doc, dict, kind)
            trigger = doc.get("on", doc.get(True))
            self.assertIsInstance(trigger, dict, kind)
            self.assertEqual(trigger["push"]["branches"], [BRANCH], kind)
            self.assertTrue(doc.get("jobs"), kind)
            for job in doc["jobs"].values():
                self.assertTrue(job.get("steps"), kind)
            self.assertIn(RUNS_ON, path.read_text(encoding="utf-8"), kind)
            self.assertIn(SLUG, doc["concurrency"]["group"], kind)

    # -- 2. 骨架正确 + 闸门有效 -------------------------------------------
    def test_story_skeleton_timeline_is_mechanically_correct(self):
        story = json.loads((self.project_dir / "story.json").read_text())
        self.assertEqual(len(story["shots"]), 45)
        self.assertEqual(story["target_duration"], 180)
        for index, shot in enumerate(story["shots"]):
            self.assertEqual(shot["id"], f"S{index + 1:02d}")
            self.assertEqual(shot["start"], index * 4)
            self.assertEqual(shot["duration"], 4)
            self.assertEqual(shot["kind"], "agnes")
            self.assertEqual((shot["seconds"], shot["frame_rate"], shot["aspect"], shot["resolution"]),
                             (7, 24, "16:9", "1080p"))
        self.assertEqual([c["start"] for c in story["chapters"]], [0, 30, 60, 90, 120, 150])
        self.assertEqual(sum(chapter["duration"] for chapter in story["chapters"]), 180)
        # 4 秒网格落在 30 秒章节上：N01 -> S01..S08（0–28 s），S09 从 32 s 起属于 N02，S45 属于 N06
        self.assertEqual(story["shots"][0]["narration_id"], "N01")
        self.assertEqual(story["shots"][7]["narration_id"], "N01")
        self.assertEqual(story["shots"][8]["narration_id"], "N02")
        self.assertEqual(story["shots"][44]["narration_id"], "N06")
        self.assertEqual(len({shot["seed"] for shot in story["shots"]}), 45)

    def test_validate_blocks_the_empty_skeleton(self):
        generator = load_module("scaffold_generate_gate", self.project_dir / "generate.py")
        story = json.loads((self.project_dir / "story.json").read_text())
        # 提示词与 style_prefix 都是空的：validate() 必须抛错，不许去烧生成额度。
        # 空提示词由 agnes_video.build_payload 先拦（Fatal），其余结构性错误是 ValueError。
        with self.assertRaises((ValueError, agnes_video.Fatal)) as caught:
            generator.validate(story)
        self.assertIn("prompt", str(caught.exception).lower())

    def test_validate_passes_once_the_plan_is_written(self):
        generator = load_module("scaffold_generate_filled", self.project_dir / "generate.py")
        story = json.loads((self.project_dir / "story.json").read_text())
        story["style_prefix"] = "Hand-drawn 2D animated documentary, muted palette, 16:9. "
        for shot in story["shots"]:
            shot["prompt"] = f"a wide establishing shot of a foggy street, unit {shot['id']}"
        for chapter in story["chapters"]:
            chapter["title"] = "章节"
            chapter["text"] = "解说词占位，实际写作时按一百二十到一百四十字填写。"
        generator.validate(story)              # 填完必须放行
        for shot in story["shots"]:
            payload = generator.full_payload(story, shot)
            self.assertEqual(payload["model"], "agnes-video-v2.0")
            self.assertEqual((payload["num_frames"] - 1) % 8, 0)

    def test_narration_manifest_is_bound_to_the_chapter_ids(self):
        story = json.loads((self.project_dir / "story.json").read_text())
        manifest = json.loads((self.project_dir / "audio/manifest.json").read_text())
        self.assertEqual([clip["id"] for clip in manifest["clips"]],
                         [chapter["id"] for chapter in story["chapters"]])
        for clip in manifest["clips"]:
            self.assertEqual(clip["sha256"], "")   # 没配音就是空，generate.py 会拒绝
            self.assertEqual(clip["text"], "")

    # -- 3. 模板 render.py / build_story.py 的守卫 ---------------------------
    def test_render_cuts_skeleton_covers_every_shot_exactly_once(self):
        render = load_module("scaffold_render", self.project_dir / "render.py")
        story = json.loads((self.project_dir / "story.json").read_text())
        self.assertEqual(sorted(render.CUTS), [f"N{i:02d}" for i in range(1, 7)])
        used = []
        for cue, entries in render.CUTS.items():
            self.assertEqual(entries[0][0], 0, f"{cue} 的第一个切点必须是 0")
            for offset, shot_id, variant in entries:
                self.assertEqual(variant, "")
                self.assertIsInstance(offset, (int, float))
                used.append(shot_id)
        self.assertEqual(used, [shot["id"] for shot in story["shots"]])
        self.assertEqual(render.DURATION, 180.0)
        self.assertEqual(render.TOTAL_FRAMES, 5400)
        self.assertEqual(render.END_AT, 180.0 - render.END_CARD)

    def test_make_edl_rejects_shot_reuse_and_accepts_the_skeleton(self):
        render = load_module("scaffold_render_edl", self.project_dir / "render.py")
        story = json.loads((self.project_dir / "story.json").read_text())
        narration = []
        start = render.INTRO
        for chapter in story["chapters"]:
            narration.append({"id": chapter["id"], "start": start, "duration": 28.0, "tempo": 1.0})
            start += 28.0 + render.GAP
        edl = render.make_edl(story, narration)
        self.assertEqual(edl[-1]["id"], "END")
        self.assertEqual(len(edl), 46)
        self.assertEqual(edl[0]["start_frame"], 0)
        self.assertEqual(edl[-1]["end_frame"], render.TOTAL_FRAMES)
        # 复用一个镜头：必须被拒绝，而不是悄悄出片
        original = render.CUTS["N06"]
        render.CUTS["N06"] = [(0, "S01", ""), *original[1:]]
        try:
            with self.assertRaises(RuntimeError) as caught:
                render.make_edl(story, narration)
            self.assertIn("只用一次", str(caught.exception))
        finally:
            render.CUTS["N06"] = original

    def test_cards_come_from_presentation_and_missing_copy_fails_loudly(self):
        render = load_module("scaffold_render_cards", self.project_dir / "render.py")
        try:
            render.find_font()
        except Exception as exc:  # 本机没有中日韩字体时跳过（Actions 运行器装了 fonts-noto-cjk）
            self.skipTest(f"no CJK font available: {exc}")
        out = self.tmp / "cards"
        presentation = {"card_header": "案件档案 / TEST", "cards": {"S05": ["大标题", "第一行", "第二行"]},
                        "end_card": ["提问读者的一句话？", "案名 · 年代", "金句", "资料来源"]}
        card = render.card_image("S05", "", out, presentation)
        end = render.card_image("END", "", out, presentation)
        from PIL import Image
        for path in (card, end):
            self.assertTrue(path.is_file())
            self.assertEqual(Image.open(path).size, (1920, 1080))
        with self.assertRaises(RuntimeError):
            render.card_image("S06", "", out, presentation)
        with self.assertRaises(RuntimeError):
            render.card_image("END", "", self.tmp / "cards2", {"cards": {}})

    def test_build_story_template_writes_presentation_and_publish_copy(self):
        # 在一个独立副本上跑，不污染其它测试读取的骨架
        project = self.production / "buildtest"
        new_topic.scaffold("buildtest", TITLE, BRANCH, project, REFERENCE)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        run = subprocess.run([sys.executable, "build_story.py"], cwd=project, capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("TODO", run.stderr, "骨架里的 TODO 必须被提醒")
        story = json.loads((project / "story.json").read_text())
        self.assertEqual(len(story["shots"]), 45)
        self.assertEqual([s["id"] for s in story["shots"]], [f"S{i:02d}" for i in range(1, 46)])
        for key in ("card_header", "card_footer", "cards", "title_card", "end_card",
                    "caption_keywords", "label_overrides", "sfx_events"):
            self.assertIn(key, story["presentation"], key)
        manifest = json.loads((project / "audio/manifest.json").read_text())
        self.assertEqual([c["text"] for c in manifest["clips"]], [c["text"] for c in story["chapters"]])
        run = subprocess.run([sys.executable, "build_story.py", "--publish"], cwd=project,
                             capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        publish = (project / "抖音发布文案.md").read_text()
        for heading in ("## 题目", "## 抖音介绍", "## 提问读者一句话"):
            self.assertIn(heading, publish)

    # -- 4. 参考项目不许被动 ----------------------------------------------
    def test_reference_project_is_untouched(self):
        # 脚手架运行前后，参考项目每个文件的哈希必须完全一致。
        # （不能用 git status：参考项目里允许另外提交审片记录这类新文件。）
        self.assertEqual(_hash_tree(REFERENCE), self.reference_before,
                         "脚手架不允许修改已交付的参考项目")

    def test_scaffold_refuses_to_overwrite_an_existing_project(self):
        with self.assertRaises(SystemExit):
            new_topic.scaffold(SLUG, TITLE, BRANCH, self.project_dir, REFERENCE)


if __name__ == "__main__":
    unittest.main()
