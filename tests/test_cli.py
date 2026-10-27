"""命令行入口的冒烟测试，防止 --list 之类的旁路功能被必填参数挡住。"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cost_calc.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestCli(unittest.TestCase):
    def test_list_works_without_finals(self):
        r = run("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("lite_480", r.stdout)

    def test_missing_finals_errors(self):
        r = run()
        self.assertNotEqual(r.returncode, 0)

    def test_basic_run(self):
        r = run("--finals", "10", "--seconds", "5", "--upgrade", "2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("分层", r.stdout)

    def test_json_output_is_parseable(self):
        import json
        r = run("--finals", "10", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("scenarios", data)
        self.assertAlmostEqual(data["baseline_all_2k"], 40.0)


if __name__ == "__main__":
    unittest.main()
