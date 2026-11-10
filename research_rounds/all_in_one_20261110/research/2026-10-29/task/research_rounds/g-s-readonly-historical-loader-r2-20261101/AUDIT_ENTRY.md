# 只读loader R2：仅修两项AMEND-FIRST输入缺陷

原包`../g-s-readonly-historical-loader-20261101/`保持原样，原loader SHA `ffd54547982e12cd1a6682531887a720246017d32b60ccf6c0b86a75cd5dee44`，原输入包SHA `d0b618d9689e1b8f782776ae3b3405875e8c48aa1f01ddd6d614bef5b804d8c4`。`original-error-report/`复制旧报告与冻结清单；`audit-evidence/`复制独审AUDIT、STRUCTURE_METADATA_CAUSALITY、SCOPE_IDENTITY_MISMATCH原证据。旧报告对前视覆盖的表述由本修正取代，旧错误产物不删除、不回填。

本轮账户创建/金融事件/买卖意图/指标重算均为0；没有修改R4、F1内核或任何原数值输入，没有进入金融前缀。

## 修正一：结构身份归实际已知观察，不归未来区间

旧实现以全两日前缀的E0 True区间`start/end`定位calendar cutoff。未来E0继续True时end被延长，停牌缺行的过去cutoff便能获得结构；未来E0改为False并重建metadata时同一过去结构反而消失。

R2 schema=`GS-READONLY-CURSOR-2`，不再接收旧interval结构。导出器`structure_observations(sid, full_saved_facts, retained_observation_days)`沿原已存E0 target和segment生成起点ID，并逐**实际观察日**保存`observed_day/identity/segment_id/e0_target`。不生成未来依赖的end字段。`stock()`先取cutoff前原最后已知facts，再用该条facts的**observed_day精确查结构**；缺失/重复或target/segment不同即拒绝，不按未来记录填补。

实际反例002683：2022-01-04 OPEN的signal cutoff为2021-12-31，实际最后facts为2021-12-17；结构为该观察已知的`002683.SZ|0|2021-10-22`。这不是伪造12/31行情、观测新鲜度或可执行资格。原股票Q/H1/availability等保持独立不变。把1/4、1/5 E0改为False，并从真实完整原states重建metadata，整个1/4 OPEN输入包保持一致；只留过去metadata也得到同一已知结构。

该修正还消除了旧interval在缺行处错误返回None的情况：2022两日前缀5个股票×事件包、2025前缀13个股票×事件包的structure字段变化（不是18个独立机会/成交）；逐条差异见VERIFICATION。除此字段及下述scope外，全包投影逐值不变。

## 修正二：F1原scope绑定种子身份

不再从行业代码拼`NATIVE1709_industry_*`。准备时逐节点直接取已审bootstrap catalogue/seed的`original_F1_scope`；运行时对每一观察强核`node_id→seed.original_F1_scope→F1 State.scope`及policy_scope一致。半导体保留`NATIVE1709_semiconductor`，电子化学品保留`NATIVE1709_electronic_chemicals`。两窗口共8条别名错误修正；总364条观察逐行核同。原Source、proof、ordinal、sequence和全部bootstrap字节未改。错误scope即使重新计算了有效文件SHA，也会语义拒绝。

## 产物与受影响回归

- 新输入：`input-v1/<2022|2025_26>/MANIFEST.json`；每窗仅metadata、f1_observations两份内容及manifest/schema变动。facts、CP1、canonical receipts、H1/PVR及NA、raw、权息、rules、protocol、selection、legacy industry、bootstrap的文件SHA全部与原包一致。
- `validation-001/VERIFICATION.json`：11项受影响检查通过。完整两日前缀四类输入包的其余字段投影、两日priority与bootstrap核同；全部实际结构观察匹配facts；364条scope核同；原反例的未来E0+派生metadata扰动；真实首日文件物理截断、重建metadata、新进程整包核同；有效SHA的错误scope拒绝；inactive/segment restart/缺行common-prefix合成。
- `validation-future-workers/VERIFICATION.json`：两窗口未来派生扰动包再由独立进程读取，整个首OPEN、priority和bootstrap核同。
- `SOURCE_FREEZE.json`、`INPUT_PACKAGE_SHA256.json`、`DELIVERABLE_SHA256.json`：冻结本轮源码、输入包与交付。

已核的H1/PVR NA、资格分解、229/262收据、9权息不重开研究；本轮以原数值文件哈希不变及完整包非目标字段投影核同复用其证据。新输入准备不等于金融接线或金融前缀获准。R4真实receipt/source绑定、调度/ACT、原生权息/支付及其显式unsupported边界仍须后续单独验收。

命令（输出目录须尚不存在）：

```sh
/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python -B research_rounds/g-s-readonly-historical-loader-r2-20261101/verify_amendment.py --out /tmp/gs-loader-r2-independent-fresh
```
