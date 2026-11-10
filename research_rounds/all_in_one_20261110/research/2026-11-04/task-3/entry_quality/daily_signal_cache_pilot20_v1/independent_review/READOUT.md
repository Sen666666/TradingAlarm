# 20股每日原信号缓存：静态独审与最小验证矩阵

静态有界PASS：在相同起点、mask、source/复权版本及合法输入域下，亲读的E0/B4/G1/I运算未见显式未来价读取、centered窗口或backfill。当前没有运行任何模型、前缀测试或账户；这不是20股实测PASS，更不是1054日全部截断重算一致证明。

## 精确源码依据

- [stock_signal.py:25](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:25)：先eligible_prices，空返回，28行assert单segment；29–46调用numeric/participation/E0、B4 evidence/G1、G1_I；47–55只返回原19字段。
- [B4 model.py:85](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:85)：log价仅相对本段首价，112行diff；163–178按t推进EW pace和过去63/21窗口。195–255候选锚/信用/确认逐行更新，最多每尺度每观察一次确认，没有后来确认回写到锚日。
- [evidence.py:176](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:176)：按显式segment分开，价格/event/strength三种clock不同；184–226逐当前观察写事实。227–235 B4 attrs/ledger只附加元数据，不喂过去行。
- [grade.py:13](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:13)：G1只维护previous_grade/prior_extreme/prior_s21，段变重置，缺strength行未知且不推进；61行仅当前结果更新记忆。
- [policy.py:99](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:99) 与 [policies_g1.py:20](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:20)：旧floor先检，再ratchet/entry，exited禁止同日再入。当前decline_candidate=False，未启用额外participation回收。

逐行片段见SOURCE_EXCERPTS.md；11原源码身份对既存freeze核同，SOURCE_SHA256.json记录本次读取字节。数值界（E0 gamma4/B4 32eps）不能在新cache中重新统一或改成近似价格容差。

## 先区分三种核同

|层|必须比较|只能声称什么|
|---|---|---|
|全日导出|20股一次full calculate所返回的每一19列行/NA mask，与序列化再读回逐行相同|存储/切片/拼接正确，不是独立重算每个历史日|
|旧三日期|同source/起点/代码的旧2022Jan24、2024Sep24、2026Jan15全部20请求；缺行/无效/未预热独列|最多60个旧目标日对照，不代表1054日|
|物理截断|每股2个已固定截点，重新calculate仅<=t输入，再比较全部共同prefix19列，不只末行|有限因果性实测；没有测试到的截点仍不能叫穷尽证明|

正式cache只算一次完整源前缀到2026May15；验证调用另计，不能用“20次正式生成”掩盖验证费用。建议40个截断调用：每股第65个strength有效观察（包含此前64未知行）+2022后本股观察序列的固定中位内部点（须有后续观察）。暖机早于2022的baseline行应至少保留到验证结束，不能先删掉导致无处比较。若样本不足，明确WARMUP_NOT_CROSSED/NO_INTERIOR_CUT，不换表现更好日期。完整提案已存VALIDATION_MATRIX_PROPOSAL.json，本审未执行。

另最多8个去重真实边界截点：首次I进入/G1升暖或blocked升级；旧线退出；若存在则旧线退出+up同日；缺量的有效价格及次有效观察；价格invalid/缺行及下一valid行；真正source段变化。可从固定20股的源/状态事实按时间选首个，不按利润选。若无真实fixture，写NOT_EXERCISED，不能用“没有遇到”冒称分支已通过。20正式full+40常规prefix+最多8边界，最多68个原calculate调用是提案成本，不是本轮已运行次数。

## 必须保留的边界

1. 当前入口单段限制是真的。底层B4/evidence/E0/project能分段，不等于stock_signal入口已能接多段。不得把多个真实source改成常数segment0以绕过assert。当前固定版本无多段可只注明NOT_EXERCISED；后来真多段时按原合同拒绝/停该股，不能擅改算法。
2. eligible_prices先移除price-invalid行；缺volume但价格有效行继续进入E0价格clock，不能跟B4/event一起跳过。每日研究导出要区分原有效返回行、MISSING_BAR、INVALID_PRICE、WARMUP；不在原表的日期不能用last value或ffill伪造当日新信号。1054只是全源日期并集，不是每股都有1054有效观察或官方交易日历。
3. B4 [model.py:280](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:280) 的attrs.terminal是整个已输入段末态；315–320的source_discontinuity档案也不属于更早每日状态。E0末条open/resolved/waiting ledger随截点会变。不能将full-run最终terminal或后来resolved outcome广播给历史行。原stock_signal返回19本来不含这些元数据；可另存末态，不拿它做每日信号。
4. 全输入索引/segment校验会检查未来后缀是否非法；未来新增重复日期/段ID会令整帧拒绝，不能把这种合法域变化说成历史值泄漏。因果对照须相同已接受source、起点、mask及代码版本；缺真实known_at仍不认证PIT。
5. qfq历史因子后来修订会改变已保存过去输入，必须作废受影响股票cache或另立版本；“同一full数据里prefix一致”不证明当年可得。输入prefix内容hash、source/version/mask/起点与代码SHA不能只记文件路径/mtime。
6. 当前设计是batch once→按日lookup，尚不是状态checkpoint增量恢复。E0极值/floor、B4 anchor/credit/EW pace、G1前级别等可早于63日；只留最近63日重启会改规则。后续增量需另审，不在本试点静态PASS内。

即使全部上述有限实测通过，也应写“20股全日导出逐行核同+旧三日期核同+指定前缀矩阵通过”。若要声称20股每一天各自从头重算均相同，需穷尽逐日物理截断，或另有独立审查的完整等价证明；本提案不作此声明。无账户、无资金/退出规则变更，不由cache正确性推导可交易性或预测能力。
