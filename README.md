# minimax-h3-budget-video

一个给 AI Agent 用的 **Skill**：用 MiniMax H3（海螺 / Hailuo）批量做视频时，把单条 5 秒片的成本从 **¥4 压到 ¥1–2**，并且知道什么时候该压、什么时候不该压。

[![CI](https://github.com/unrealinux/minimax-h3-budget-video/actions/workflows/ci.yml/badge.svg)](https://github.com/unrealinux/minimax-h3-budget-video/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 它解决什么问题

网上大部分「H3 省钱攻略」都建立在同一个误解上：以为 2K 是更高档的生成，所以「先用 768P 试，再升级 2K」能打折。

实际上 H3 的 2K 是**二次再生成**——768P 的结果连同原始上下文再跑一遍 `H3-Regenerate-2K`。官方定价：

```
768P ¥0.50/s + Regenerate ¥0.30/s = 2K ¥0.80/s
```

**两条路完全等价，一分不省。**

这个 skill 就是从这个事实出发，把真正的省钱杠杆找出来：

| 杠杆 | 效果 | 代价 |
|---|---|---|
| 交付降到 768P + 后期超分 | **−37.5%** | 1080p 投放几乎看不出差别 |
| 换渠道（fal Turbo） | **−78%** | 需外币卡，768P 上限 |
| 只对部分镜头升级 2K | **−30%**（按 20% 升级率） | 需要人工挑选 |
| 草稿用 Lite 480P | 视返工率，**可能为负** | 过片率高时纯属浪费 |

最后一条是关键：草稿不是免费的。一条 480P 草稿 ¥0.80，一次 2K 重跑 ¥4.00，**每 5 条草稿至少要避免 1 次全价重跑才回本**。skill 会把这条账算给你看，而不是无脑建议「先跑草稿」。

## 计算器

```bash
python3 scripts/cost_calc.py --finals 20 --seconds 5 --upgrade 3 --drafts 30
```

```
规模：20 条成片 × 5.0s，草稿 30 条，2K 升级 3 条

方案                                                总价       vs 全 2K
--------------------------------------------------------------------
全量 2K（直接生成）                                   ¥80.00            基准
全量 768P（后期超分）                                 ¥50.00 -30.00 (-38%)
分层：768P 打底 + 选择性 2K                           ¥54.50 -25.50 (-32%)
草稿优先：480P 试错 + 768P 定稿 + 选择性 2K               ¥78.50   -1.50 (-2%)
fal Turbo（768P，美元结算）                          ¥17.88 -62.12 (-78%)
混渠道：fal 出 768P + 官方升级 2K                      ¥22.38 -57.62 (-72%)
Replicate 2K（美元结算）                            ¥92.95 +12.95 (+16%)
```

纯标准库，无依赖，Python 3.8+。

## 安装

**直接 clone 到 skills 目录（推荐）**

```bash
git clone git@github.com:unrealinux/minimax-h3-budget-video.git \
  ~/.agents/skills/minimax-h3-budget-video
```

仓库根目录就是 skill 本身，`SKILL.md` 在顶层，clone 完即可被 Agent 识别。

**手动安装**

把 `SKILL.md`、`references/`、`scripts/` 复制到任意 skills 目录即可，没有运行时依赖。

## 用法

装好之后直接说需求就会触发：

> 我要做 20 条 5 秒的护肤品竖屏广告，预算尽量低，但要有 3 条 2K 母版给投放用。

Agent 会先问三个问题（交付分辨率 / 是否有外币支付 / 是否需要跨镜头一致性），然后给出档位、渠道、条数和报价。

也可以只用计算器，不装 skill：

```bash
python3 scripts/cost_calc.py --help
python3 scripts/cost_calc.py --finals 30 --seconds 5 --upgrade 6 --fal-mode ref
```

## 目录结构

```text
.
├── SKILL.md                 # 主流程：认知前提 → 价格阶梯 → 流水线 → 提示词 → 常见错误
├── prices.json              # 价格唯一来源（官方 + 第三方）
├── references/
│   ├── pricing.md           # 官方 7 档价目 + fal/Replicate 对比 + 核验方法
│   └── prompting.md         # 六段式模板 + 正反例 + 三种崩坏修复
├── scripts/
│   ├── cost_calc.py         # 成本计算器
│   └── check_prices.py      # 价格核验：抓线上页面对比 prices.json
├── tests/                   # 单元测试 + 页面解析 fixture
├── evals/                   # 触发与输出质量的测试用例
└── .github/workflows/
    ├── ci.yml               # 每次 push 跑测试
    └── price-check.yml      # 每周一自动核验价格，有变动就开 issue
```

## 价格核验

`prices.json` 是唯一价格来源，`cost_calc.py` 从它读取。核验脚本会抓三个线上来源并逐项对比：

```bash
python3 scripts/check_prices.py            # 有变动退出码 1，抓取失败退出码 2
python3 scripts/check_prices.py --update   # 确认后写回 prices.json
python3 scripts/check_prices.py --report r.md
```

数据来源：

| 来源 | 抓什么 |
|---|---|
| `platform.minimaxi.com/document/price` | 官方 7 档每秒单价、输入视频/图片单价 |
| `fal.ai/models/*` | 页面内嵌的 `billing_unit.price` 字段（比定价页准） |
| `replicate.com/minimax/h3` | 768P / 2K 每秒单价 |

GitHub Actions 每周一自动跑一次。发现变动会开一个 issue 并附上差异表；解析失败会开另一个 issue 提醒你页面结构变了。确认后跑 `--update` 提交即可。

这套机制存在的意义：fal 的定价页和实际计费字段曾经就不一致（$0.03 vs $0.05），只信定价页会算错预算。

## 价格时效性

**价格数据快照：2026-10-27。** MiniMax 调价比较频繁，正式采购前请先跑一次核验：

```bash
python3 scripts/check_prices.py
```

脚本会抓官方页、fal 模型页和 Replicate，逐项对比 `prices.json`。如果输出「全部一致」就可以直接用；有差异时先看差异表，确认后 `--update` 并提交。

三处来源不一致时以**实测账单**为准（跑一条 5 秒请求反推单价）。

## Roadmap

- [x] 价格自动核验脚本（抓官方页 + fal 计费字段，输出 diff）
- [ ] fal / Replicate 最小调用示例
- [ ] 扩展到 FLUX 3 Max / Wan 3.0 的横向选型
- [ ] 触发描述优化（避免只问价格也被拉进来）
- [ ] 真实案例库：不同品类的 prompt 与成片对比

## 贡献

Issue 和 PR 都欢迎，尤其是：

- 价格变动（请附核验截图或账单）
- 新的崩坏模式与修复写法
- 其他渠道的实测单价

## License

[MIT](LICENSE)
