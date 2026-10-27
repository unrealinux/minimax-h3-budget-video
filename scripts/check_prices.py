#!/usr/bin/env python3
"""核验线上价格与 prices.json 是否一致。

用法：
    python scripts/check_prices.py                 # 检查，有变动则退出码 1
    python scripts/check_prices.py --update        # 把线上价写回 prices.json
    python scripts/check_prices.py --report r.md   # 同时输出 markdown 报告
    python scripts/check_prices.py --json          # 机器可读输出

设计原则：
- 只依赖标准库，CI 里不需要装任何东西。
- 抓不到就报错，不要静默跳过——静默跳过会让价格悄悄过期。
- 解析失败和价格变动是两种不同的失败，退出码分开（2 / 1）。
"""

import argparse
import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICE_FILE = ROOT / "prices.json"

OFFICIAL_URL = "https://platform.minimaxi.com/document/price"
FAL_BASE = "https://fal.ai/models/"
FAL_ENDPOINTS = {
    "fal_turbo": "minimax/h3-max-turbo/text-to-video",
    "fal_turbo_ref": "minimax/h3-max-turbo/reference-to-video",
    "fal_h3": "minimax/h3/text-to-video",
}
REPLICATE_URL = "https://replicate.com/minimax/h3"

UA = "Mozilla/5.0 (compatible; minimax-h3-price-check/1.0)"

# 官方表格里 (模型, 分辨率) → prices.json 的键
OFFICIAL_KEYS = {
    ("MiniMax-H3", "2K"): "h3_2k",
    ("MiniMax-H3", "768P"): "h3_768",
    ("MiniMax-H3-Highspeed", "768P"): "highspeed_768",
    ("MiniMax-H3-Lite", "768P"): "lite_768",
    ("MiniMax-H3-Lite", "480P"): "lite_480",
    ("MiniMax-H3-Max", "480P"): "max_480",
}

ANCHOR = re.compile(
    r"(MiniMax-H3-Regeneration|MiniMax-H3-Highspeed|MiniMax-H3-Lite|MiniMax-H3-Max|MiniMax-H3)\b"
)
ROW = re.compile(r"(2K|768P|480P)\s*¥([\d.]+)\s*¥([\d.]+)\s*¥([\d.]+)")
REGEN_ROW = re.compile(r"768P\s*→\s*2K\s*¥([\d.]+)")


class FetchError(Exception):
    pass


class ParseError(Exception):
    pass


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"{url} 抓取失败：{exc}") from exc


def html_to_text(html):
    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def parse_official(text):
    """从官方定价页文本里抽取 H3 各档单价（元/秒）。"""
    starts = [m.start() for m in re.finditer("H3 系列旗舰模型", text)]
    if not starts:
        raise ParseError("找不到「H3 系列旗舰模型」标题，页面结构可能变了")

    start = starts[-1]
    end = text.find("Context-IR", start)
    segment = text[start:end] if end > start else text[start:]

    blocks = {}
    matches = list(ANCHOR.finditer(segment))
    if not matches:
        raise ParseError("价格区块里找不到任何 MiniMax-H3 模型名")

    for i, m in enumerate(matches):
        name = m.group(1)
        tail = segment[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(segment)]
        rows = blocks.setdefault(name, {})
        for res, out_price, in_video, in_image in ROW.findall(tail):
            rows.setdefault(res, (float(out_price), float(in_video), float(in_image)))

    result = {}
    for (model, res), key in OFFICIAL_KEYS.items():
        rows = blocks.get(model, {})
        if res in rows:
            result[key] = rows[res][0]

    h3_768 = blocks.get("MiniMax-H3", {}).get("768P")
    if h3_768:
        result["input_video_h3"] = h3_768[1]
    max_768 = blocks.get("MiniMax-H3-Max", {}).get("768P")
    if max_768:
        result["input_video_max_768"] = max_768[1]

    regen = blocks.get("MiniMax-H3-Regeneration", {})
    if "2K" in regen:
        result["regen_2k"] = regen["2K"][0]
    else:
        m = REGEN_ROW.search(segment)
        if m:
            result["regen_2k"] = float(m.group(1))

    if len(result) < 5:
        raise ParseError(f"只解析出 {len(result)} 个价格，页面结构可能变了：{sorted(result)}")
    return result


def parse_fal(html):
    """从 fal 模型页内嵌的 billing 字段取实际计费价（美元/秒）。"""
    idx = html.find("billing_unit")
    if idx < 0:
        raise ParseError("页面里没有 billing_unit 字段")
    window = html[idx: idx + 300]
    m = re.search(r'price\\?"?:([\d.]+)', window)
    if not m:
        raise ParseError("billing_unit 附近找不到 price 字段")
    return float(m.group(1))


def parse_replicate(text):
    m = re.search(
        r"768P outputs cost \$([\d.]+) per second, and 2K outputs cost \$([\d.]+)",
        text,
    )
    if not m:
        raise ParseError("找不到 Replicate 的计费说明")
    return {"replicate_768": float(m.group(1)), "replicate_2k": float(m.group(2))}


def collect(timeout=30):
    """抓取所有来源，返回 (抓到的价格, 错误列表)。"""
    fetched, errors = {}, []

    try:
        official = parse_official(html_to_text(fetch(OFFICIAL_URL, timeout)))
        fetched.update(official)
    except (FetchError, ParseError) as exc:
        errors.append(f"official: {exc}")

    for key, endpoint in FAL_ENDPOINTS.items():
        try:
            fetched[key] = parse_fal(fetch(FAL_BASE + endpoint, timeout))
        except (FetchError, ParseError) as exc:
            errors.append(f"fal/{key}: {exc}")

    try:
        fetched.update(parse_replicate(html_to_text(fetch(REPLICATE_URL, timeout))))
    except (FetchError, ParseError) as exc:
        errors.append(f"replicate: {exc}")

    return fetched, errors


def compare(expected, fetched):
    diffs = []
    for section, values in expected.items():
        if not isinstance(values, dict):
            continue
        for key, old in values.items():
            if key not in fetched:
                continue
            new = fetched[key]
            if abs(new - old) > 1e-9:
                diffs.append({
                    "section": section,
                    "key": key,
                    "old": old,
                    "new": new,
                    "change": (new - old) / old * 100 if old else 0.0,
                })
    return diffs


def render(diffs, errors, checked):
    lines = []
    if diffs:
        lines.append(f"{'键':<24}{'仓库值':>10}{'线上值':>10}{'变动':>10}")
        lines.append("-" * 56)
        for d in diffs:
            lines.append(
                f"{d['key']:<24}{d['old']:>10.3f}{d['new']:>10.3f}{d['change']:>+9.1f}%"
            )
    if errors:
        lines.append("")
        lines.append("抓取/解析失败：")
        for e in errors:
            lines.append(f"  - {e}")
    if not diffs and not errors:
        lines.append(f"全部一致（已核验 {checked} 项）。")
    return "\n".join(lines)


def render_markdown(diffs, errors, checked, updated):
    md = [f"## 价格核验报告（{updated}）", ""]
    if diffs:
        md += ["| 键 | 仓库值 | 线上值 | 变动 |", "|---|---|---|---|"]
        for d in diffs:
            md.append(f"| `{d['key']}` | {d['old']:.3f} | {d['new']:.3f} | {d['change']:+.1f}% |")
    else:
        md.append(f"未发现价格变动（已核验 {checked} 项）。")
    if errors:
        md += ["", "**抓取或解析失败：**", ""]
        md += [f"- {e}" for e in errors]
    return "\n".join(md)


def main():
    p = argparse.ArgumentParser(description="核验线上价格与 prices.json 是否一致")
    p.add_argument("--update", action="store_true", help="把线上价写回 prices.json")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--report", metavar="FILE", help="额外输出 markdown 报告")
    p.add_argument("--timeout", type=int, default=30, help="单次请求超时秒数")
    args = p.parse_args()

    expected = json.loads(PRICE_FILE.read_text(encoding="utf-8"))
    fetched, errors = collect(args.timeout)
    diffs = compare(expected, fetched)

    tracked = set()
    for v in expected.values():
        if isinstance(v, dict):
            tracked |= set(v)
    checked = len(tracked & set(fetched))
    today = datetime.date.today().isoformat()

    if args.update and diffs:
        for d in diffs:
            expected[d["section"]][d["key"]] = d["new"]
        expected["updated"] = today
        PRICE_FILE.write_text(
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"已更新 {len(diffs)} 项，写入 {PRICE_FILE.name}")

    if args.report:
        report = render_markdown(diffs, errors, checked, today)
        Path(args.report).write_text(report + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(
            {"diffs": diffs, "errors": errors, "checked": checked, "fetched": fetched},
            ensure_ascii=False, indent=2,
        ))
    else:
        print(render(diffs, errors, checked))

    if errors:
        return 2
    if diffs and not args.update:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
