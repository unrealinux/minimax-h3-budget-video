"""价格核验脚本的解析测试。

用真实页面的结构片段做 fixture，避免"测试通过但线上解析不出来"。
"""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

spec = importlib.util.spec_from_file_location("check_prices", ROOT / "scripts" / "check_prices.py")
check_prices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_prices)


class TestOfficialParser(unittest.TestCase):
    def setUp(self):
        html = (FIXTURES / "official_price.html").read_text(encoding="utf-8")
        self.prices = check_prices.parse_official(check_prices.html_to_text(html))

    def test_all_tiers_parsed(self):
        self.assertEqual(self.prices["h3_2k"], 0.80)
        self.assertEqual(self.prices["h3_768"], 0.50)
        self.assertEqual(self.prices["highspeed_768"], 0.40)
        self.assertEqual(self.prices["lite_768"], 0.26)
        self.assertEqual(self.prices["lite_480"], 0.16)
        self.assertEqual(self.prices["max_480"], 0.33)

    def test_input_video_is_not_image_price(self):
        """曾经把图片单价 ¥0.20 误当成输入视频价，这里锁死。"""
        self.assertEqual(self.prices["input_video_h3"], 0.50)
        self.assertEqual(self.prices["input_video_max_768"], 0.97)

    def test_regeneration_price(self):
        self.assertEqual(self.prices["regen_2k"], 0.30)

    def test_garbage_raises(self):
        with self.assertRaises(check_prices.ParseError):
            check_prices.parse_official("这是一个没有价格表的页面")


class TestFalParser(unittest.TestCase):
    def test_reads_billing_field(self):
        html = (FIXTURES / "fal_page.html").read_text(encoding="utf-8")
        self.assertEqual(check_prices.parse_fal(html), 0.025)

    def test_missing_billing_raises(self):
        with self.assertRaises(check_prices.ParseError):
            check_prices.parse_fal("<html><body>no billing here</body></html>")


class TestReplicateParser(unittest.TestCase):
    def test_reads_both_resolutions(self):
        html = (FIXTURES / "replicate_page.html").read_text(encoding="utf-8")
        prices = check_prices.parse_replicate(check_prices.html_to_text(html))
        self.assertEqual(prices, {"replicate_768": 0.08, "replicate_2k": 0.13})


class TestCompare(unittest.TestCase):
    def test_detects_change(self):
        expected = {"official_cny": {"h3_2k": 0.80}}
        fetched = {"h3_2k": 0.90}
        diffs = check_prices.compare(expected, fetched)
        self.assertEqual(len(diffs), 1)
        self.assertAlmostEqual(diffs[0]["change"], 12.5)

    def test_ignores_missing_keys(self):
        expected = {"official_cny": {"h3_2k": 0.80, "regen_2k": 0.30}}
        fetched = {"h3_2k": 0.80}
        self.assertEqual(check_prices.compare(expected, fetched), [])

    def test_no_change(self):
        expected = {"third_party_usd": {"fal_turbo": 0.025}}
        self.assertEqual(check_prices.compare(expected, {"fal_turbo": 0.025}), [])


class TestPriceFileContract(unittest.TestCase):
    """prices.json 的键必须覆盖计算器用到的全部价格。"""

    REQUIRED_CNY = {
        "lite_480", "lite_768", "max_480", "highspeed_768",
        "h3_768", "h3_2k", "regen_2k", "input_video_h3", "input_video_max_768",
    }
    REQUIRED_USD = {"fal_turbo", "fal_turbo_ref", "fal_h3", "replicate_768", "replicate_2k"}

    def test_keys_present(self):
        data = json.loads((ROOT / "prices.json").read_text(encoding="utf-8"))
        self.assertTrue(self.REQUIRED_CNY <= set(data["official_cny"]))
        self.assertTrue(self.REQUIRED_USD <= set(data["third_party_usd"]))
        self.assertIn("updated", data)


if __name__ == "__main__":
    unittest.main()
