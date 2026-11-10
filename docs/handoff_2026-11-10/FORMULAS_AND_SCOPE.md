# 当前 51 分类与公式索引

源 B：`/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1`。
源 E：`/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1`。
对应本地快照为 `snapshots/20261109_sector51/`、`snapshots/20261106_entry/`。以下是接手摘要，精确定义以列出的冻结合同和实施补充为准，不以早期设计覆盖最终实施。

## 1 分类和样本

51 类包含“未分类”。固定研究池 1709 股中，1692 股进入 50 个具名行业，17 股未分类排除。不是 51 个均参与交易行业，不是历史时点全 A 股。

全部分类：中药、互联网电商、交通运输与物流、光伏风电设备、光学电子、农牧养殖、动力电池、化学制药、化工材料、医疗器械、医疗服务、医药商业、半导体、商贸零售、基建工程、基础耗材与包装、家电家居、工程咨询与专业服务、建筑建材、房地产开发、旅游酒店、服装纺织、未分类、机械设备、汽车整车、汽车零部件、油气能源、消费电子、游戏传媒、煤炭、环保设备与服务、珠宝饰品、生物制品、电力公用、电子元件材料、电气电网设备、白酒、社会服务、综合企业、美容护理、自动化与机器人、计算机设备、证券保险、轨交军工装备、软件与IT服务、通信设备、通信运营服务、金属钢铁、银行、食品饮料、饲料动保。

关键映射：

- 证券保险=D061+D062，不含 D063 多元金融。
- 未分类=BC8B、C6DA、D063、D0A6。
- 软件与IT服务=BC9C、BC9D、C6AC。
- 半导体=BCA5、BCA6、C6EC、C6ED、C6EE、D0B8、D0B9。
- 动力电池=BC8C、BC8D、BC8E。
- 光伏风电设备=BC8F、BC90、BC91、BC92、BC93、BC94、BC95。
- 银行=C6D6、C6D7、C6D8、C6D9。

证券保险/银行/半导体在当前完整分类中分别有53/42/190股，固定研究池参与者52/39/126股。合并行业从成员重聚合，不拼接旧日期。

权威文件：B/SECTOR51_MAPPING_RECEIVED.json（SHA256 `86144c2c9791a53d76d2b64c493f610569ca57a57ff0db0618b5b4d994557049`），B/joint51_candidate_v9_facts/{CLASSIFICATION_ALL1709.csv,EXCLUDED_UNCLASSIFIED.csv,MAPPING_QA.json,MAPPING_SOURCE_HASHES.json}。原映射主表在主工程 research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv；固定池为 E/momentum_persistence_breadth_v1/FIXED_ROSTER.csv。

## 2 基础信号

“个股 M3”与“主线版本 M3”不是同一对象。

个股 M3 为对数日收益 EMA，alpha=1/3，64 个收益观测预热；最近三个共同交易日 mu>0，且价格、成交量、来源与数据段有效一致。这里的量仅作有效性，不能称为量价强度因子。

行业固定成员 N；M3 与原 PVR 共同已知 K；右侧 n；未知 U=N−K。t 与 t−3 同成员交集 J 的净扩散 d=进入−退出。行业 TRUE 下界：

`n≥3 AND [(3n≥N AND J>0 AND d>0) OR 2n≥N]`。

UNKNOWN 独立保留，不填 FALSE，不靠缩分母提高广度。

M1 起共同主线证据：

- RS5/10/20 = 100 ×（行业完整共同窗口收益中位数 − 全1692池有效窗口中位数），单位百分点。
- Q = 当前行业 M3 TRUE，且当前、上一共同收盘均 n/N≥1/2。
- S = Q AND RS10>0 AND RS20>0 AND 行业绝对10日收益中位数>0。
- F = Q AND RS5>0 AND RS5>前日RS5 AND 行业绝对5日收益中位数>0 AND 20日突破成员数×2≥N。
- M = S OR F，严格三值。
- E = max(RS5,0)×n/N，主线排序还要求 E 有限。
- 原弱化 W = 连续两收盘 RS5<0 且 RS10<0，或连续两收盘行业 M3 FALSE。它不同于 M5 的 W_alloc。

来源：B/READOUT.md §2；B/mainline_candidate_v1/FROZEN_CONTRACT_DRAFT.md。

## 3 M1 到 M7

### M1 主线优先与信息确认

主线请求先于非主线 SEED，同业 ADD 先于 SEED；ADD≤当前持仓股数，单次2%尝试NAV、整轮4%、单股10%、现金底线10%。真实费后盈利与未消费CP经CLOSE及next OPEN双重确认；资金失败不抹去信息成熟，只有真实ADD才消费CP。真实正需求且现金不足时向合资格弱仓筹资。

合同：B/mainline_candidate_v1/FROZEN_CONTRACT_DRAFT.md，必须连同 CONTRACT_APPROVAL.json、FROZEN_INPUTS.json 阅读。

### M2 零持仓保留票报价暂停

经济公式不变。已有、零持仓、因资本拒绝保留的 SEED 票可 PAUSED_NO_QUOTE；恢复核完整来源、因子、事件链，恢复 OPEN 不执行旧计划，须 CLOSE 重计划后 next OPEN。持仓缺报价仍整日原子阻断。不得以未来公告倒推当时停牌。

合同：B/mainline_candidate_v2_pending_quote_pause/CONTRACT.md。

### M3 赢家核心与行业参考资本

去除 ADD≤当前股数限制，仍保留2%单次与4%整轮。赢家核心=剩余SEED+最早剩余ADD中不超过原SEED股数的部分。

`B=NAV−10%NAV−应收−J外固定资本−全可售机动仓估计卖出损耗`；`J={M TRUE且有限E>0}`；`T_s=max(fixed_s,λE_s)`，ΣT=B。T只是上限，不制造请求；CLOSE冻结，OPEN只缩量或取消。

合同：B/mainline_candidate_v3_core_reference/CONTRACT.md。

### M4 经济试仓与行业事件

最小法定 q_econ 满足双边最低佣金额外惩罚 `surcharge(q)≤2×0.0005×q×C`。它不是全部往返费用≤10bp，后者已被SSE约10.282bp比例费下限否定。

相邻FALSE→TRUE生成行业事件；A及期间B共享事件出生NAV的2% SEED额度。代表排序=个股5日收益−行业中位数、M3连续TRUE天数、20日容量、原票日期、代码。

v2修复 UNKNOWN 行业SEED/W ADD冻结供出分类；即便旧版未实际卖，也会改变fixed/B/T，必须采用修正版作基准。

合同：B/mainline_candidate_v4_known_sector_fix_v2/CONTRACT.md。

### M5 初始核心与扩张资本分离

EVENT/RESIDUAL SEED=INITIAL；MATURE SEED与所有ADD=EXPANSION，成交后角色不升级。INITIAL仅当当前M TRUE、真实OPEN确认且整轮费后清算利润>0才是当前核心；ADD不再自动获种子等股量核心。

`W_alloc=E+max(E_t−E_prev,0)`（前值未知只用E）；`G=NAV−10%NAV−应收−ΣF−stress−ΣR`；`X_s=G×W_s/ΣW`；`T_s=F_s+X_s+R_s`。先扣固定资本下界，剩余资本竞争。无请求行业仍占纸面目标是该版局限。

合同：B/mainline_candidate_v5_expansion_competition/CONTRACT.md。

### M6 删除成熟ADD整轮4%槽

将 `B_ADD=min(0.02 NAV0,max(0,0.04 NAV0−当前整轮市值))` 改为 `B_ADD=0.02 NAV0`，NAV0不重置。M/CP、双时点正净利、现金底线、单股帽、行业T、容量、法定股数保持。允许新增本金风险，不是利润融资。

合同：B/mainline_candidate_v6_mature_round_cap/CONTRACT.md。

### M7 按真实合法需求封顶

V=行业实际市值；F=固定资本；K=V−F；R=EVENT预约。D为独立合法MATURE请求含费需求，排除reference/cash限制，但先核结构、CP、CLOSE正净利、股票帽、单CP 2% NAV0、容量、法定量；EVENT/RESIDUAL不进D。

`U=K+D`；`X_s=min(U_s,λW_s)`；`ΣX=min(max(0,G),ΣU)`；`T=F+R+X`；成熟买空间=max(0,X−K)。K不是下界；剩余G留空，不再做整数松弛分配。

合同：B/mainline_candidate_v7_demand_capped/CONTRACT.md。

## 4 M8 到 M12 独立问题

这些版本不得默认顺序叠加。M8/M9/M10及M11、M12均以M7为相应主要基线，继承少量实现代码不等于继承经济机制。

### M8 行业弱化扩张退出

收盘 sector state=0 且 M=0，将所有EXPANSION lot标记下个合法OPEN退出；INITIAL不变、UNKNOWN不触发。标记不可撤销，I/CP优先，保留T+1、法定聚合卖量。合同：mainline_candidate_v8_false_mainline_retirement/CONTRACT.md。

### M9 持续个股失败退出

P同时要求sector=0、M=0、个股M3=0、整轮净清算利润≤0且事实有效。同round相邻两共同收盘满足P才标记EXPANSION退出。净利=实际交易现金流+股息+Q×raw_close×(1−slip)−卖费。不是整户净利或单层浮盈。合同：mainline_candidate_v9_persistent_stock_failure/CONTRACT.md。

### M10 INITIAL正净利CP保护

仅实际买后当日新CP receipt可被INITIAL采用，需net_close>0且 `net_at_CP=cashflow+dividend+Q×[(F/A)×(1−slip)]−sell_fee>0`。自身seed_cp_floor只升不降，有效保护=max(account I,已采用CP floor)。采用后不因买票消费撤回。静态全轮CP正净利不保证逐层保护或跳空实际盈利。合同：mainline_candidate_v10_positive_cp_initial_protection/CONTRACT.md。

### M11 成熟新SEED结构入场

仅MATURE新SEED新增 `G=F OR CP_state`，严格三值；EVENT/RESIDUAL、持仓、ADD、退出保持。entry CP receipt_day≥原signal_day，可同日，不要求持仓盈利。CP槽须仍有效；原票/NAV/预算不重置，等待不占资金。成交只留entry_evidence_id，active.cp=None、confirmed_history=False、add_count=0，不把入场前证据伪作买后确认。

旧版numpy.bool被误作UNKNOWN，20日经济结果 INVALID_IMPLEMENTATION；修正版shadow.bool_state采用 `isinstance(value,(bool,numpy.bool_))`。合成通过不等于经济有效。

合同：mainline_structural_maturity_design_v1/DESIGN.md §3–8；mainline_candidate_v11_structural_maturity_entry_execution_fix_v2/CONTRACT_REF.md。结果用 mainline_v11_account_audit_v2，不用旧无效版。

### M12 新成熟种子不挤出既有可行用途

N=新MATURE SEED；P0=删除N后用原M7完整规划所得影子。共同锚点下健康lot H要求 `y_hat_branch≤y_hat_shadow`；合法ADD/EVENT要求 `q_hat_branch≥q_hat_shadow`。H需真实post-SEED确认、当前整轮正净利、I/CP未破、原融资字段已知，不要求当前M=1。

从最低优先级新种子逐个删除，形成最多|N|+1个完整分支；仅CLOSE通过分支可在OPEN选择。每支使用自己的receiver/donor/reference/floor/数量，禁止跨分支拼max/min。OPEN用当时可知条件预测prefix及统一H选枝，再作实际撮合；全天OHLC no_fill只能后置，不能反馈重选。保证条件可提交投影，不保证未来fill完全不挤出。

退让票 FUNDING_NONDISPLACEMENT_WAIT 保留原身份和全部preflight，不能靠删票绕开Q0、公司行动或403。

**最终权威是 mainline_winner_funding_design_v1/EXECUTION_FREEZE_ADDENDUM.md，不是早期DESIGN的主动截donor/joint-solver方案。** 对应SHA256 `3ffa6bd951e2377e65a83f9ee13bd3a2ed320970ed0f03fd277398e1b9856bd1`，另读EXECUTION_FREEZE_FIELDS.json及mainline_candidate_v12_winner_funding_competition/CONTRACT_REF.md。

现金修正版仅新增688200.SH、2024-10-11精确事件：d_cash=d_source=0.23、d_ref=0.2297。压缩分支簿与同manifest恢复是存储变化，不改经济策略。合同：mainline_candidate_v12_winner_funding_cash_688200_v2/CONTRACT.md。

## 5 更早失败不可抹去

E/READOUT.md 保存 E1、E2明确否决及E3.1语义通过。E1的箱高目标T=B+W不能充当真实潜在收益，永久第一次突破锚点会错拒后续趋势，固定冷却会错过快速收复。E2扫描5517股、63244个首次局部I事件，接纳机制被否定，不能以空队列称成功。E3.1仅通过有限语义/前缀，不是经济排序成功。这些阶段是看到反例后的修订，不是独立预注册样本外候选。

更多11/06迭代已全部建立文件索引及小型快照；查 `RESEARCH_DIRECTORY_INDEX.csv` 与原对应 READOUT/INDEPENDENT_READOUT/CONTRACT，不能只看根READOUT覆盖后续成果。
