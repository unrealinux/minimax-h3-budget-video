"""成本计算器的单元测试。

重点保护一条不变量：当所有镜头都要 2K 时，
「768P + Regenerate」必须与「直接 2K」同价（0.50 + 0.30 = 0.80）。
这条规则是整个 skill 的立论基础，被改坏会让所有建议失真。
"""

import importlib.util
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cost_calc", ROOT / "scripts" / "cost_calc.py")
cost_calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cost_calc)


def args(**kw):
    base = dict(
        finals=10,
        seconds=5.0,
        drafts=0,
        upgrade=0,
        input_video_seconds=0.0,
        input_model="h3",
        fal_mode="t2v",
    )
    base.update(kw)
    return Namespace(**base)


class TestBaseline(unittest.TestCase):
    def test_all_2k(self):
        scenarios, all_2k, _ = cost_calc.build_scenarios(args())
        self.assertAlmostEqual(all_2k, 10 * 5 * 0.80)

    def test_all_768_is_37_5_percent_cheaper(self):
        scenarios, all_2k, _ = cost_calc.build_scenarios(args())
        all_768 = next(s for s in scenarios if s["name"].startswith("全量 768P"))
        self.assertAlmostEqual(all_768["cny"] / all_2k, 0.625)


class TestStagingInvariant(unittest.TestCase):
    def test_staged_equals_all_2k_when_everything_upgraded(self):
        """全部升级 2K 时，分层与直出必须同价——没有折扣。"""
        scenarios, all_2k, _ = cost_calc.build_scenarios(args(upgrade=10))
        staged = next(s for s in scenarios if s["name"].startswith("分层"))
        self.assertAlmostEqual(staged["cny"], all_2k)

    def test_staged_cheaper_when_partial_upgrade(self):
        scenarios, all_2k, _ = cost_calc.build_scenarios(args(upgrade=2))
        staged = next(s for s in scenarios if s["name"].startswith("分层"))
        self.assertLess(staged["cny"], all_2k)
        self.assertAlmostEqual(staged["cny"], 10 * 5 * 0.50 + 2 * 5 * 0.30)

    def test_zero_upgrade_equals_all_768(self):
        scenarios, _, _ = cost_calc.build_scenarios(args(upgrade=0))
        staged = next(s for s in scenarios if s["name"].startswith("分层"))
        all_768 = next(s for s in scenarios if s["name"].startswith("全量 768P"))
        self.assertAlmostEqual(staged["cny"], all_768["cny"])


class TestDrafts(unittest.TestCase):
    def test_no_draft_scenario_when_drafts_zero(self):
        scenarios, _, _ = cost_calc.build_scenarios(args(drafts=0))
        self.assertFalse(any(s["name"].startswith("草稿优先") for s in scenarios))

    def test_draft_cost_is_priced_at_lite_480(self):
        scenarios, _, _ = cost_calc.build_scenarios(args(drafts=20, upgrade=2))
        draft = next(s for s in scenarios if s["name"].startswith("草稿优先"))
        expected = 20 * 5 * 0.16 + 10 * 5 * 0.50 + 2 * 5 * 0.30
        self.assertAlmostEqual(draft["cny"], expected)

    def test_drafts_need_five_to_pay_for_one_rerun(self):
        """一条草稿 ¥0.80，一次 2K 重跑 ¥4.00 → 每 5 条草稿必须救回 1 次重跑。"""
        ratio = cost_calc.PRICES["h3_2k"] / cost_calc.PRICES["lite_480"]
        self.assertAlmostEqual(ratio, 5.0)


class TestChannels(unittest.TestCase):
    def test_fal_turbo_is_cheaper_than_official(self):
        scenarios, all_2k, _ = cost_calc.build_scenarios(args())
        fal = next(s for s in scenarios if s["name"].startswith("fal Turbo"))
        self.assertLess(fal["cny"], all_2k)
        self.assertAlmostEqual(fal["cny"], 10 * 5 * 0.025 * cost_calc.USD_TO_CNY)

    def test_fal_reference_mode_costs_double(self):
        t2v, _, _ = cost_calc.build_scenarios(args(upgrade=2, fal_mode="t2v"))
        ref, _, _ = cost_calc.build_scenarios(args(upgrade=2, fal_mode="ref"))
        a = next(s for s in t2v if s["name"].startswith("混渠道"))
        b = next(s for s in ref if s["name"].startswith("混渠道"))
        fal_only = 10 * 5 * 0.025 * cost_calc.USD_TO_CNY
        # 参考生视频单价翻倍，升级部分不变，所以差额正好等于 t2v 的 fal 成本
        self.assertAlmostEqual(b["cny"] - a["cny"], fal_only)

    def test_mixed_adds_upgrade_on_top_of_fal(self):
        scenarios, _, _ = cost_calc.build_scenarios(args(upgrade=4, fal_mode="t2v"))
        mixed = next(s for s in scenarios if s["name"].startswith("混渠道"))
        fal_only = 10 * 5 * 0.025 * cost_calc.USD_TO_CNY
        self.assertAlmostEqual(mixed["cny"], fal_only + 4 * 5 * 0.30)


class TestInputVideo(unittest.TestCase):
    def test_input_video_charged_per_clip(self):
        _, baseline, _ = cost_calc.build_scenarios(args())
        _, with_input, input_cost = cost_calc.build_scenarios(
            args(input_video_seconds=3, input_model="h3")
        )
        # 官方价目表：H3 768P 输入视频 ¥0.50/s（不是 ¥0.20，那是图片单价）
        self.assertAlmostEqual(input_cost, 3 * 0.50 * 10)
        self.assertAlmostEqual(with_input - baseline, input_cost)

    def test_max_input_video_is_much_more_expensive(self):
        _, _, h3_cost = cost_calc.build_scenarios(args(input_video_seconds=3, input_model="h3"))
        _, _, max_cost = cost_calc.build_scenarios(args(input_video_seconds=3, input_model="max"))
        self.assertAlmostEqual(max_cost / h3_cost, 0.97 / 0.50)


if __name__ == "__main__":
    unittest.main()
