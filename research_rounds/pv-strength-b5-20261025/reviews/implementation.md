# B5核心实现记录

本实现只新增本轮 arithmetic.py、evidence.py、policy.py、api.py 与本说明。旧E0/B4源码、旧结果及登记只读，没有账户、经济评价或取数。

- arithmetic逐运算复制冻结E0的compare/log_ratio/higher，未更改gamma4或对数分支。
- evidence提取numeric.py纯事件状态direction/ext及事件计算；不运行旧numeric函数，也不运行旧participation函数，市场证据不含target/entered/exited/floor/pending。
- policy自己维护active/floor/pending及候选编号，按原E0顺序退出→判断等待响应→原事件→解决等待→必要时建新等待。事实候选没有active门控；真正创建等待由策略裁决。
- 强度直接动态加载SHA-256固定的原B4，用独立模块名，全部101列只增strength_前缀；journal['strength']为原列表，未增删收据字段。未宣称B5为新强度公式或一个统一事件核。
- run_b5返回evidence/journal/state/ledger；journal为{'events':纯事件与高参与下跌事实收据,'strength':B4原日志}。enhancements=True显式拒绝，未虚构增强策略。

三个时钟分别是price_observation（显式有效价格），event_observation（有效价格中C/V正有限），strength_observation（显式强度有效子集），均按来源段从0开始。量比窗口使用价格clock，坏量留NaN占位；missing/zero/negative/infinite量不会中断有效价格行的退出和收复处理。已准备状态在缺量的有效价格行保留。没有任何正量的段提供稳定schema、ready=0与event=0，是B5的显式适配扩展，不能称原numeric接受该输入。

priceinvalid行保留输入、来源与两valid标志，E0事实及策略输出未知，不推进任一clock。最终接口中state原int64列统一为nullable Int64，保证不因未来出现invalid行而改变前缀schema；原有Int64/string/float64保持。对照旧state时明确将旧int64转为Int64后逐位比较，不能声称未转换的原dtype完全相同。ledger保持原dtype，在各段独立结尾保留open等待，不伪造边界reject，segment_id追加于原字段末尾。

输入沿B4检查日期与非回返来源段；额外强制一天最多一行、有效OHLC合法及strengthmask为pricemask子集，属于B5日线适配合同收紧，没有更改B4旧入口。只保留显式八个输入列，避免报告旧e0_*或策略列通过元数据透传进入证据。

有限本地自测结果将在完成后追加；正式全量技术核验由独立测试与主agent执行。

第一次67观察本地自测于state精确对齐处失败：`AssertionError: (<BusinessDay>, None)`。原因是新输出reindex恢复了输入的BusinessDay freq，而旧participation从行日期建索引后freq=None。修正仅令state索引按行日期重建，保留旧dtype与索引元数据合同；没有修改机制。此失败发生在正式冻结/真实输出前，未删除或掩盖。

修正后的有限自测stdout：

```text
PASS 67-observation low=98 exact event/state/ledger; final target=0 exited=1; strength removed identity
PASS 67-observation low=94 exact event/state/ledger; final target=1 exited=0; strength removed identity
PASS missing-volume reclaim and following price row exact state/ledger
PASS adapter empty rows 0 evidence columns 131
PASS adapter all_price_invalid rows 67 evidence columns 131
PASS adapter all_volume_missing rows 67 evidence columns 131
PASS adapter strength_disabled rows 67 evidence columns 131
```

独立静态审查另发现段身份字符串化碰撞（例如整数1与字符串'1'）及policy独立入口缺少日内重复/空白段检查。预冻结接口修复：允许原整数段，但拒绝两个不同段字符串化后重名；policy同步日线日期、空白段和重复列校验。此为B5适配入口合同，不修改B4或E0冻结计算。

独立测试在预冻结发现state整数dtype此前依赖全输入是否含invalid行，因而可能随未来行改变前缀schema。按主agent决定统一输出nullable Int64；上方首次自测stdout记录的是修复前已全部有效输入的原dtype直接对齐，最终验证必须显式归一化旧整数表示。另补充policy独立入口事实完整性：有效价行ready/declined/high_effort/decline_candidate只接受非缺失0/1，event只接受-1/0/1，避免bool(NaN)被误当True。

最终预冻结限量自测stdout：

```text
PASS final schema low=98: exact E0 state after explicit int64->Int64; ledger exact unchanged
PASS final schema low=94: exact E0 state after explicit int64->Int64; ledger exact unchanged
PASS future invalid row cannot change valid-prefix state dtype or values
PASS int0/string0 source identity collision rejected
PASS policy rejects missing binary facts and event on valid price rows
PASS standalone policy rejects empty source identity and intraday daily duplicates
```

这些仅是固定67观察与接口微型检查，不能替代后续正式真实序列、物理前缀、独立数学或架构核验。未计算收益，未以任何结果选择阈值。
