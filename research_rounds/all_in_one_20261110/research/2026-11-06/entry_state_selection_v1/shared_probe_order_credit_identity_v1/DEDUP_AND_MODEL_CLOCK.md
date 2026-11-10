# 查重与已存在的删失模型

本次有限源码与报告检索，不声称穷尽所有聊天/研究目录。

## 入口近邻
- pvr_formula_contribution_v1/formula_HISTORY_MATH_AUDIT.md：PVR时钟、尺度不辨识、21项旧记忆，损伤/去饱和/保留贡献等大范围排重。
- fast_q1_signal_mechanism_v1/READOUT.md：已明确I失效不重置PVR；原新根floor高于前根floor也有固定检验。
- entry_protection_migration_mechanism_v1/READOUT.md：Q=log(I_t/I_t-3)/log(C_t/I_t)排序，无晋升证据且损尾。
- m3_q1_entry_path_strata_v1/READOUT.md：年龄、CP、21涨幅、I距离、波动、当日价量自然分层，弱季没有简单35%组。
- m3_native_leg_full_coverage_v1/READOUT.md：19795邀请原leg UP门，Q1无改善分离且拒真尾。
- lagged_amount_order_preflight_v1/READOUT.md：相邻日价格/金额交叉差40例，无支持。
- causal_entry_start_structure_v1/READOUT.md：原确认极点修复、前3日量价参与，不支持共同成熟门。
- mature_theory_evidence_inventory_v1/READOUT.md：成熟理论的不同证据等级，不能把排序融合失败说成整套理论均已公平失败。
- shared_ab_entry_selection_attribution_v1/READOUT.md：已有共享分母、早期池风险占用、首单风险减半预留5→6的研究。本次未重复调风险额度。

## 已实施竞争风险
目录：selection_entry_diagnosis_v1/actual_round_probability_v1/competing_risk_v1
已直接读SUMMARY.json、FINAL_AUDIT_NOTES.json、run_competing_risk_at_fit.py、run_competing_risk.py。

旧模型：
h+(a|x)=exp(α+,bin(a)+β+·x)/Z
h−(a|x)=exp(α−,bin(a)+β−·x)/Z
h0=1/Z；Z=1+exp(η+)+exp(η−)
年龄段1–5、6–20、21–60、61–120，H=120。
在cut前已买、cut前未闭者，只贡献截至cut前的continue暴露；cut前已闭且T≤H才记正/非正退出。预测F±(H)=ΣS(a−1)h±(a)，S=Πh0。
已有36个月拟合、1652预测、1545成熟配对；第一训练cut2023-01，758回合含70个H前右删失。22参数特征模型，8参数截距基线。四个未来退出/标签投毒检查训练counts不变。
特征为PVR、保护距离/既往波动、sigma20、市场breadth20/delta5、mobile角色、原i_buy，非当前P/D/C。
旧结果没有建立正概率辨别优势，也不是新资金收益。

## P/D/C金额风险已实际实施
marked_return_tilt_pilot_v1/READOUT.md / PROTOCOL.md
五特征PVR、Wilder14DMI、CMF21及两交互。x只取原信号CLOSE；当时风险集含正常在险、冻结U、退出金额待定M。完整ordinary净金额Y=NET/3000保留实值：
η=β·z；
Z_g=q0,g+qU,g+qM,g+Σ_j qj,g exp(ηYj)
L=Σ_i,g n_ig logZ_g−Σ_known η_iYi+0.5β'diag(4,4,4,16,16)β。
U/M的金额充分统计0不等于把其真实净额归零。已卖清M不继续当持仓生存；未知仍未知；H120不是强平。
2024-09/10/11/12四cut真实风险集3477/4015/4319/4437，成熟ordinary2736/2786/2914/3178，U/M/S全部列明。
它不只是已闭二元分类器，也不是缺少右删失意识。
当前有限H预测仍不识别全出生无限期净额，不识别U故障后的终局。借换IPCW/Cox/Fine–Gray名字无法自动修复这些识别条件。

## 仍需避免的混同
- PRICE与当前M3 A+B是不同入口、保护、队列和责任模板。
- 旧独立/实际获资域的模型标签不等于当前共享被拒候选在新状态下的回合标签。
- 当前全账UNKNOWN冻结是资源与证据状态，不应伪装为独立行政删失。
- 35%完整最终净正与F_positive(H)是不同estimand。
本轮模型fits=0、H scans=0、accounts=0。
