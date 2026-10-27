#!/usr/bin/env python3
"""MiniMax H3 成本计算器。

用法示例：
    python cost_calc.py --finals 30 --seconds 5 --drafts 30 --upgrade 6
    python cost_calc.py --finals 12 --seconds 5 --drafts 0 --upgrade 0 --json

价格数据日期：2026-10-27，来源见 references/pricing.md。
改动价格请只改 PRICES，不要散落在计算逻辑里。
"""

import argparse
import json
import sys

# 人民币 / 秒
PRICES = {
    "lite_480": 0.16,
    "lite_768": 0.26,
    "max_480": 0.33,
    "highspeed_768": 0.40,
    "h3_768": 0.50,
    "h3_2k": 0.80,
    "regen_2k": 0.30,
    "input_video_h3": 0.20,
    "input_video_max_768": 0.97,
}

# 美元 / 秒
PRICES_USD = {
    "fal_turbo": 0.025,
    "fal_turbo_ref": 0.05,
    "fal_h3": 0.05,
    "replicate_768": 0.08,
    "replicate_2k": 0.13,
}

USD_TO_CNY = 7.15


def cny(usd):
    return usd * USD_TO_CNY


def build_scenarios(args):
    s = args.seconds
    n = args.finals
    d = args.drafts
    u = args.upgrade

    input_cost = 0.0
    if args.input_video_seconds > 0:
        rate = PRICES["input_video_max_768"] if args.input_model == "max" else PRICES["input_video_h3"]
        input_cost = args.input_video_seconds * rate * n

    scenarios = []

    all_2k = n * s * PRICES["h3_2k"] + input_cost
    scenarios.append({
        "name": "全量 2K（直接生成）",
        "detail": f"{n} 条 × {s}s × ¥{PRICES['h3_2k']}/s",
        "cny": all_2k,
    })

    all_768 = n * s * PRICES["h3_768"] + input_cost
    scenarios.append({
        "name": "全量 768P（后期超分）",
        "detail": f"{n} 条 × {s}s × ¥{PRICES['h3_768']}/s",
        "cny": all_768,
    })

    staged = n * s * PRICES["h3_768"] + u * s * PRICES["regen_2k"] + input_cost
    scenarios.append({
        "name": "分层：768P 打底 + 选择性 2K",
        "detail": f"{n} 条 768P + {u} 条 Regenerate",
        "cny": staged,
    })

    if d > 0:
        draft_first = (
            d * s * PRICES["lite_480"]
            + n * s * PRICES["h3_768"]
            + u * s * PRICES["regen_2k"]
            + input_cost
        )
        scenarios.append({
            "name": "草稿优先：480P 试错 + 768P 定稿 + 选择性 2K",
            "detail": f"{d} 条 480P 草稿 + {n} 条 768P + {u} 条 Regenerate",
            "cny": draft_first,
        })

    fal_turbo = cny(n * s * PRICES_USD["fal_turbo"])
    scenarios.append({
        "name": "fal Turbo（768P，美元结算）",
        "detail": f"{n} 条 × {s}s × ${PRICES_USD['fal_turbo']}/s",
        "cny": fal_turbo,
    })

    fal_rate = PRICES_USD["fal_turbo_ref"] if args.fal_mode == "ref" else PRICES_USD["fal_turbo"]
    mixed = cny(n * s * fal_rate) + u * s * PRICES["regen_2k"]
    scenarios.append({
        "name": "混渠道：fal 出 768P + 官方升级 2K",
        "detail": f"{n} 条 fal（${fal_rate}/s）+ {u} 条官方 Regenerate",
        "cny": mixed,
    })

    replicate_2k = cny(n * s * PRICES_USD["replicate_2k"])
    scenarios.append({
        "name": "Replicate 2K（美元结算）",
        "detail": f"{n} 条 × {s}s × ${PRICES_USD['replicate_2k']}/s",
        "cny": replicate_2k,
    })

    return scenarios, all_2k, input_cost


def main():
    p = argparse.ArgumentParser(description="MiniMax H3 成本计算器")
    p.add_argument("--finals", type=int, required=True, help="最终成片条数")
    p.add_argument("--seconds", type=float, default=5, help="每条时长（秒），默认 5")
    p.add_argument("--drafts", type=int, default=0, help="480P 草稿条数，默认 0")
    p.add_argument("--upgrade", type=int, default=0, help="需要 2K 母版的条数，默认 0")
    p.add_argument("--input-video-seconds", type=float, default=0,
                   help="每条片子的参考输入视频时长（秒），默认 0")
    p.add_argument("--input-model", choices=["h3", "max"], default="h3",
                   help="参考输入视频按哪个模型计费，默认 h3")
    p.add_argument("--fal-mode", choices=["t2v", "ref"], default="t2v",
                   help="fal Turbo 的用法：t2v（$0.025/s）或 ref 参考生视频（$0.05/s）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--list", action="store_true", help="打印价格表后退出")
    args = p.parse_args()

    if args.list:
        print("人民币/秒：")
        for k, v in PRICES.items():
            print(f"  {k:<22} ¥{v}")
        print("美元/秒：")
        for k, v in PRICES_USD.items():
            print(f"  {k:<22} ${v}")
        return

    if args.upgrade > args.finals:
        sys.exit("--upgrade 不能大于 --finals")
    if 0 < args.drafts < args.finals:
        print(f"提示：草稿数（{args.drafts}）少于成片数（{args.finals}），"
              f"草稿优先方案的草稿成本会偏低。\n")

    scenarios, all_2k, input_cost = build_scenarios(args)

    if args.json:
        print(json.dumps({
            "input": vars(args),
            "scenarios": scenarios,
            "baseline_all_2k": all_2k,
            "input_video_cost": input_cost,
        }, ensure_ascii=False, indent=2))
        return

    print(f"\n规模：{args.finals} 条成片 × {args.seconds}s"
          f"，草稿 {args.drafts} 条，2K 升级 {args.upgrade} 条")
    if input_cost:
        print(f"参考视频输入成本已计入：¥{input_cost:.2f}")
    print()

    print(f"{'方案':<40}{'总价':>12}{'vs 全 2K':>14}")
    print("-" * 68)

    for sc in scenarios:
        delta = sc["cny"] - all_2k
        if all_2k:
            pct = delta / all_2k * 100
            delta_s = "基准" if abs(delta) < 1e-9 else f"{delta:+.2f} ({pct:+.0f}%)"
        else:
            delta_s = "-"
        print(f"{sc['name']:<40}{'¥' + format(sc['cny'], '.2f'):>12}{delta_s:>14}")

    print()
    print("判断要点：")
    if args.upgrade < args.finals:
        print(f"  · 只有 {args.upgrade}/{args.finals} 条需要 2K，分层方案必然优于全量 2K。")
    else:
        print("  · 全部镜头都要 2K 时，分层与直接 2K 总价相同（0.50+0.30=0.80），没有折扣。")
    if args.drafts:
        breakeven = PRICES["h3_2k"] / PRICES["lite_480"]
        print(f"  · 草稿每 {breakeven:.0f} 条至少要避免 1 次 2K 重跑才回本。")
    print(f"  · 单条 2K 均价：¥{all_2k / args.finals:.2f}")


if __name__ == "__main__":
    main()
