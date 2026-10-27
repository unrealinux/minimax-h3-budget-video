# Changelog

## 0.2.0 — 2026-10-27

### 新增

- `prices.json`：价格唯一来源，计算器和核验脚本都从它读取
- `scripts/check_prices.py`：抓官方页 / fal 模型页 / Replicate，逐项对比，支持 `--update` 和 `--report`
- `.github/workflows/price-check.yml`：每周一自动核验，有变动或解析失败自动开 issue
- 解析测试（fixture 来自真实页面结构），测试数 23 → 34

### 修复

- **输入视频单价写错**：官方表格里 H3 输入视频是 ¥0.50/s（768P）、¥0.80/s（2K），此前误写成 ¥0.20/s（那其实是输入图片单价）。受影响的 `ref2v` 成本估算已更正。
- `cost_calc.py --list` 不再要求 `--finals`

## 0.1.0 — 2026-10-27

首个版本。

- `SKILL.md`：认知前提（2K 是二次再生成、分层不省钱）、官方价格阶梯、四步流水线、六段式提示词、常见错误表、自建判断
- `references/pricing.md`：官方 7 档价目、fal / Replicate 渠道对比、价格核验方法
- `references/prompting.md`：提示词模板、正反例、三种崩坏修复
- `scripts/cost_calc.py`：成本计算器，支持草稿、选择性升级、混渠道、参考视频计费
- `tests/`：13 个单元测试，锁定「全部升级时分层与直出同价」这一核心不变量
- `evals/`：4 个真实场景测试用例

### 已知问题

- fal 定价页与模型页内嵌计费字段存在不一致（$0.03/$0.015 vs $0.05/$0.025），已按模型页为准并在文档中标注
- 跨渠道升级（fal 出 768P → 官方 Regenerate）未经实测，文档中按「需先验证」处理
