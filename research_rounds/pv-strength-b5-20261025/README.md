# B5：证据与策略分离，E0兼容验证完成

**关闭增强规则后，在本轮15条冻结历史和可对照合成样例中，入场、退出、保护点及其余E0政策字段逐值100%一致；完整合成/边界验收通过。** 整段无有效量等原函数会拒绝的扩展边界单列，不宣称与旧函数输出相等。本轮没有账户回测，没有新增行情，没有更改原E0或B4。

- [完整算法与接口规范](../../docs/ALGORITHM_B5.md)
- [结论、逐标的核验与边界](CONCLUSION.md)
- [事前协议](PROTOCOL.md)、[生产和初版验证冻结](freeze.json)、[仅验证器v2冻结](freeze-validation-v2.json)
- [正式真实结果](results-v2/summary.json)：15条、35,590行、35,587有效价格观察、60物理前缀，0差异。
- [技术核验](validation/technical-run-v2/verification.json)：184/184；20原事件合成、12明确注入的政策单测、2来源重置派生。
- [独立架构审查](reviews/architecture.md)：35/35；[验证器审查](reviews/audit/validator-v2/REVIEW.md)：23/23。
- [验证器失败与修复](validation/VALIDATOR_REPAIR.md)：初版完整保留；[v1/v2输出身份](reviews/real-output-v1-v2.json)证明45张表和15份日志文件SHA完全相同，模型输出没有变化。
- `registry.json`、`output-contract.json`、`complete.json`登记版本、输出与最终证据身份。

## 本版做了什么

量价层抽出原E0纯事件计算，提供极点、放量下跌候选及最低价/收复价，另提供原样B4强度。参与策略只消费这份证据，自行管理E0入退、支持和pending；它可以在全部strength列被删除后独立运行。不是调用旧E0的target冒充新策略，也不是把旧参与函数藏在事实层。

本轮强度公式不变，仍继承B4的方向/推进/结构/冲击分工及其迟滞等限制。增强参与规则尚未定义；`enhancements=True`明确拒绝。不得把兼容成功写成增强后收益已提高。

## 文件入口与复现

生产代码为 `code/arithmetic.py`、`code/evidence.py`、`code/policy.py`、`code/api.py`。验证v2在 `code-validation-v2/`；原code中的初版验证器和原失败保留。正式有效结果为 `results-v2/` 和 `validation/technical-run-v2/`，不要覆盖它们。

如确需重放兼容检查，给出尚不存在的新目录；只运行信号技术核验，不运行账户：

```sh
PYTHONDONTWRITEBYTECODE=1 TradingAlarm/research/.venv/bin/python \
  research_rounds/pv-strength-b5-20261025/code-validation-v2/verify_real.py \
  --output research_rounds/pv-strength-b5-20261025/results-reproduction-new
```

15来源含同一ETF不同冻结版本，属于已见开发历史，不能当成15个独立样本。原7条比较保留原有效观察口径（AU0三条旧零量记录仍排除）；缺量但有效价格的行为另由原E0适配与明确合成检验覆盖。

本轮到此完成，不自动开展增强规则、选股、仓位、换仓或账户回测。
