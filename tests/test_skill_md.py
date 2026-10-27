"""校验 SKILL.md 的结构，避免改了文件却忘了改元数据。"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    data = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


class TestSkillMetadata(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")
        self.meta = parse_frontmatter(self.text)

    def test_frontmatter_exists(self):
        self.assertTrue(self.meta, "SKILL.md 缺少 YAML frontmatter")

    def test_name_matches_directory(self):
        self.assertEqual(self.meta.get("name"), ROOT.name)

    def test_name_is_slug(self):
        self.assertRegex(self.meta.get("name", ""), r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_description_is_present_and_specific(self):
        desc = self.meta.get("description", "")
        self.assertGreater(len(desc), 120, "description 太短，触发率会很低")
        self.assertIn("MiniMax H3", desc)

    def test_body_is_reasonably_sized(self):
        self.assertLess(len(self.text.splitlines()), 500)


class TestReferencedFiles(unittest.TestCase):
    def test_reference_and_script_paths_exist(self):
        text = SKILL.read_text(encoding="utf-8")
        paths = re.findall(r"`((?:references|scripts)/[\w./-]+)`", text)
        self.assertTrue(paths, "SKILL.md 没有引用任何参考文件")
        for p in paths:
            self.assertTrue((ROOT / p).exists(), f"引用了不存在的文件：{p}")


if __name__ == "__main__":
    unittest.main()
