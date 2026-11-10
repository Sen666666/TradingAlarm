# 688200.SH 单条本地事件与 M12 原预检边界独立审查

结论：PASS_EXACT_688200_20241011_LOCAL_RESEARCH_EVENT_ADMISSION。82 项独立检查通过，事实准入无剩余阻断。此报告不执行事件入库，不批准历史重跑，不改变任何冻结输入。

## 原阻断合理，不是影子候选集合扩张

M12 2024-10-11 的恢复态明确为 held_qty=0、pending=true、RETAINED。688200 的真实票于 2024-09-26 发起，原生 EVENT 首次资金拒绝后保留；2024-10-10 pending 中仍有同一票的 MATURE SEED，planned_q=200、_ref_q=0。原 active∪pending∪live_tickets 已包含该票，毋须加入分支并集。V12 atomic_step:433 先执行继承的 economic_preflight，之后才 select_open。没有筛选后绕过原 guard。

原 M7 同 ticket_id 在 10/8 因 attempt_budget 取消，M12 当时原非现金检查 PASS 后进入资金 WAIT。已保存原预算分别为 25727.850299564335810 与 25958.763539444864810，夹住 builder 独算的 200 股全部成本 25939.808894736；本审查独立确认两份预算及生命周期，不把成本值另称独立费率复算。资金路径差异使 M12 在公司行动当天仍有合法旧票，而不是 guard 扩大到无关证券。

joint51_candidate_v11_suspension_accounting/engine.py:166-184 的原 guard 对目标存在行动而未准入即阻断。allocation_ablation_v1/allocation_rules.py:120-146 明确 Q0 旧票也必须核桥，reviewed pending-entry bridge 不产生股息。故 22 日认证后原子停下符合冻结合同，不应跳过预检或凭 _ref_q=0、未持仓忽略行动。

## 唯一准入事实

- 唯一标识：688200.SH | 2024-10-11 | 688200.SH|LOCAL_DISTRIBUTION_007。
- 公告 2024-044，署名及已缓存公告记录日期 2024-09-27；登记 2024-10-10，除息及现金发放均为 2024-10-11。
- 纯现金，不转增、不送股；每普通有权登记股 d_cash=0.23 元。回购专户 176100 股不参与；自行发放对象为无。
- 总股本 135439427，参与 135263327，总现金 31110565.21。摊薄额 0.229700951186…，公告明确官方参考减项 d_ref=0.2297。
- 独立从原 PDF 经本机已安装 PDFKit 只读提取 5 页完整文本，与封存 txt 的完整字符串及 SHA 相同。未安装程序、未联网、未更改 PDF；不声称视觉页面复核。
- 六项来源 hash 全部吻合：PDF、封存全文、CNINFO 缓存查询、688200 行动源、signal.parquet、NOTICE_REVIEW_INPUT。另核单条 adapter SHA af9b6319597e47ea858c0125bf0e43d31c270da056e06db8d470d76bdc025686。
- 原 October 26 条 manifest 未包含本条，因此此前 FACT_REVIEW 的独立准入待审标记确实尚未解除，不能将旧 PASS 当成既准入。

## 因子桥与适用范围

从冻结 signal.parquet 直接读到同源、有效的 10/10 与 10/11 两行：
factor_old=2.234495011354039，factor_new=2.2388548166866773，previous_close=118.11。
用 d_source=0.23 独算 fo×pc/(pc-d_source)/fn−1 = 9.9145105249E-17，小于 1E-11。
误用 d_ref=0.2297 则残差 −0.0000025449545003559778435690，不能替代源坐标桥。

只允许新增本条精确元组，继续使用既有纯现金 loader 的日期、唯一行动、同源、源项和因子断言，不放宽其他行动或日期。d_source、d_cash、d_ref 三者不可混用。

原始 Q0 ticket 纯函数测试确认：缺桥仍拒绝；加入精确 reviewed 桥后只改变 current_factor/last_verified_day，原身份、NAV、budget、floor、phase 等全部保留，record_qty=0、dividend_accrual=0。保存持仓与订单显示此票此前从未实际买入，故 10/10 登记权益为零，无应收、派现、现金或股数增加。不得重置尝试、凭事件开新轮或自动买入。已有 NET80 仅为研究约定，不能宣称公告统一按 80% 发放；本票零权益不受该税务近似影响。

公告日期早于登记/除息，但晚于该票 9/26 初始信号。允许按原记录日及生效日引用，不得向 9/26 信号或先前 CLOSE 选择倒灌公告与未来因子。本审查不认证全数据 PIT、实际税务或实盘可用。

## 交付与下一步

可复验脚本 review_688200_event.py，结果 V12_688200_EVENT_ADMISSION_QA.json。两者均在当前独立 review 目录；31 个原候选 source hash 复核全通过。没有构建策略 Data，没有运行历史或网络，没有修改策略、原事件输入或已封存 M12 输出。

若另开精确 Data adapter，须引用本报告与唯一 adapter/source hashes，保持原 guard、经济方法和 atomic 行为。新的单次实验仍须另行封存批准；本报告仅补齐此事件事实准入证据。
