# B4固定化与E0分层兼容核验

2026-10-25，用户授权暂时固定B4，整理完整算法，核查仅凭B4能否用简单策略100%复现E0。不改算法，不跑账户，不取数。

- [完整B4规范](../../docs/ALGORITHM_B4.md)：输入、公式、初始状态、递推顺序、事件、量证据、数值边界、未知处理、输出与限制。
- [E0兼容结论与反例](E0_COMPATIBILITY.md)：仅用当前B4原生输出无法精确复现E0；B4不是E0的严格增量超集。E0含明确参与政策，用户的向后兼容检验作为项目要求成立。
- `registry.json`：固定B4名称、源码与规范身份，连接原研究冻结清单。
- `output-contract.json`：从冻结核心源码读取的完整字段清单，不包括报告join的E0对照列。
- `validation/compat-output-v1/`：一组67观察双路径反例，B4完全相同而E0退出不同；六物理前缀核验。
- `reviews/`：空白agent独立源码/反例/文档审查。
- `validation/before-identity.json`、`validation/after-identity.json`：本轮前后核查旧B4 342文件、核心15文件、旧强度736文件及E0/R/R1登记30文件不变。

本次固定的是现有研究版本，不是声明成熟或授权交易。没有新强度模型，没有B4→E0策略实现；未来兼容架构仅记录，不能误写为已通过全历史等价测试。旧报告仍为 http://127.0.0.1:8788/report/ ，原研究目录不修改。

如需复现技术反例，指定未存在的输出目录，不能覆盖本轮证据：

```sh
PYTHONDONTWRITEBYTECODE=1 TradingAlarm/research/.venv/bin/python \
  research_rounds/b4-baseline-contract-20261025/validation/prove_b4_e0_information_loss.py \
  --output research_rounds/b4-baseline-contract-20261025/validation/compat-reproduction-new
```

该命令仅跑冻结指标与E0信号函数，不导入账户引擎。完成本轮后不自动启动兼容重构、策略阈值搜索或账户队列。
