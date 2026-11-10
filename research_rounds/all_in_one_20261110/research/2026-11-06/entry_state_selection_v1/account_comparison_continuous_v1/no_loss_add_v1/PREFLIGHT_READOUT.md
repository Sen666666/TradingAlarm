# 单PVR剩余成本加仓门预检

run_no_loss_add.py单臂原PVR_SLOT1，原120万元空仓、原ACT初态，仅安装profit_gate。没有E3导入或排名变化；Q=0保留原资格，Q>0要求Q×已知O×0.9995−dated估计卖费严格大于剩余平均含买费成本K。卖出同比减K，股息不抵K，送转只改Q。原路由资格/迁移/风险预算均保留。

完成preflight_20220207_v3，窗口2022-01-01至2022-02-07。2022-02-07 OPEN重启、当前及未来HLCV扰动后全部mutable payload哈希相等。独立成本簿从全journal重建相等：cursor349=journal349，216成本事件，109股票状态，所有数量等于最终层合计。2402门判定，其中24负判定；负判定不等于确定阻止原本可成交的订单。详细来源checkpoint SHA见INDEPENDENT_COST_RESTART_CHECK.json。

早先preflight_20220207在输入加载时主动停止以加入额外断言；v2建账户前遇有限end晚IPO因子边界错误。v3因子源保持原全期C.END，--end仅限制事件窗口，已经通过。旧目录保留，不覆盖。

driver、profit_gate、test_profit_gate在v3之后冻结。当前未启动全期，交由父统一执行。

正式推荐：research/.venv/bin/python run_no_loss_add.py --out run_1200000，默认end=2026-05-15；禁止已有目录覆盖。

完成后独立分析：research/.venv/bin/python analyze_comparison.py --run ./run_1200000 --out ./comparison_1200000。需在本目录运行或使用绝对路径。脚本要求完整DONE，读源哈希、原baseline PVR与新单PVR数据，不创建账户。

分析产物包括年度NAV/回撤/库存、每日ACT及暴露、完整0→0回合与清仓年份胜率/盈亏比、未平损益、特定两期间、冻结big60事件前6日实际持仓参与和权重/增失、gate负判定去重股票日、funding仅门原因与多原因拒绝分列、原价已亏平与微盈不足滑点费用分类。跨年完整回合全部损益归清仓年仅供交易统计，不与年度NAV损益直接桥；重复成本不是节省现金。股息应收不称到账，继承原付款时点现金假设。

固定未来1709池、O±5bp代理不保证可成交、公司行动条款预先已知；big60只事后标签。分析脚本已经语法检查，完整新结果尚未产生，未假称经济分析完成。
