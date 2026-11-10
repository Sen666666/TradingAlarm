# 首日52只与后续修订：历史事实核查

## 结论
不是没有研究或没有任何实现；但没有找到把“空仓统一试探、盈利后扩张、全账户试错总额度”一起接入原1709连续账户并完成全期验证的修复版。已有全期 no_loss_add 只修已有仓亏损禁加，首日52笔完全没变。近期 ACT/DMI 又回到原未带盈利门的基线做单因素比较，不能把它们说成用户最终策略的迭代结果。

## 最早对话证据（UTC；北京时间加8小时）
- 2026-11-01 10:34:56，消息 Sentinel_476f1f9361b88191a89c7c06a6b608f6：已指出“机动仓＋确认资金池”联动、行业确认不等于个股值得扩张；下一步仍是设计和审查。
- 2026-11-05 05:02:03，Sentinel_5d668767f22c8191b1611370f2da4a0a：已明确 confirmed 确认行业推进，不是股票试仓成功，并说明 No60移除了全账户3%风险门。
- 2026-11-06 03:21:10，Sentinel_6121fc5faca48191bada73ba1de4283b：承诺禁止整体亏损持仓加仓。
- 2026-11-06 06:36:46，Sentinel_f3b53e11501c8191b692421838a43a31：报告 no_loss_add 完整账户结果，胜率25.70%→25.63%，NAV多约1825元，MDD47.72%→43.93%。
- 2026-11-06 08:18:18，Sentinel_983a7f17e1ec81918d0c045643da8e24：首次查到明确52首仓报告；08:18:46 Sentinel_ba72dacbac548191a7b83f1b011c4840 更正1/4信号、1/5成交；08:21:19 Sentinel_7a02d5db6ef08191a51120a25f28443e 补充空仓初始化效应。
- 2026-11-08 21:10:09，Sentinel_76180a19c7908191895c522db7b47468：向用户明确去ACT基线未带盈利加仓门。
不将搜索到的首条52消息等同本地最早计算时刻。

## 首日直接重读封存记录
原PVR与no_loss_add的2022-01-05 52笔成交所有字段完全相同。3笔CORE从probe获资，49笔空仓MOBILE从confirmed获资；49笔买款1049465.41047元，全52笔1079633.48697元、费355.763490294239元。
当日CLOSE 52层全部在confirmed，库存市值1075362.74元，NAV1195373.489539705761元，约89.9604%。不能说52笔都是直接confirmed成交。
证据 FIRST_DAY_COMPARISON.json；读取日期必须看记录at，不能全文匹配嵌套layer opened字段。

## 各版本实际做到什么
1. account_comparison_continuous_v1/no_loss_add_v1：完整2022-01-01—2026-05-15、120万元、1054日、DONE和独审已完成。profit_gate.py:48 Q=0直接允许新门；:53–60仅给原No60路由添持仓净清算盈利条件。资格、迁池和原预算不改。期末1256421.55元对1254596.96元；不是集中首仓修复。
2. risk_pyramid_bounded_v1、capital_sequence_v2：四只已知日线路径的隔离资金草案。后者含日新增金额10%、新试风险0.25%、总股票准入60%、共享试错账，但READOUT:5及132明确未接完整原生账户。不能称全期修复。
3. actual_account_add_capacity_v1/growth_continuous_78_v1、growth_no_qcap_78_v1：2023-01-03—04-28、78日连续实验，继承no_loss_add 2022末状态；确实实现成长风险公式及一次取消q_add<=Q的对照。但growth_adapter.py:106–109空仓恒真，:117保留NoConfirmed60Budget。首探和confirmed空仓路线未修。原/成长/无股数帽同窗收益24.8599%/19.6679%/20.6609%；不是全期总仓制度验证。
4. mobile_first_probe_protection_v1/conditional_paths_v1：14个独立单股条件路径，2%首探、0.25%风险及盈利加仓；保留原池路由，种子之后原CORE仍可10%。不是共享全账户/全部首仓修复。
5. act_only_ablation_continuous_v1：唯一禁ACT强平暂停，其余旧规则不动。ablation_support.py:18–28为唯一dispatch；:87–94明示旧No60、无account_risk、record_only。原PVR exact复现；首个经济分叉2022-04-22，故首日52不变。
6. native_dmi_two_month_continuous_v1及native_dmi_january_followthrough_v1：同日同业同角色槽换DMI顺序，仍原ACT、原空仓路线、原预算且无盈利加仓门。不是继承no_loss_add的最终策略。

## 代码根因
W/account-risk-ablation-20261031/route_without_account_check.py:8–10初始probe；mobile且行业level>0时尝试迁池并增confirmed路。:24–26择可获最大合法股数，不要求已有该股库存。2026-11-04/task/pvr_pool_feasibility/component.py:17–27继承无account-risk模型，再删除confirmed60；native_adapter.py:11–22安装该预算。continuous_inputs.py:13–15导入此适配器。
旧池仍有现金底线、probe10%/风险0.5%、行业风险1%、行业资本、单股10%等约束，不能说“完全无风险限制”。52笔/初始化本身不证明错误；实际不一致在总仓及首探与已验证扩张未分责。

## 尚未完成的事项
需要明确新账户的空仓试探身份和所有新试探共享风险/金额预算，与行业授权分开；盈利才加仓应作为继承约束，不是重新可选因子。先做首日及后续重入/迁池回归，再在同一冻结日线执行合同下验证全期。具体额度仍需设计，不能把本报告当新参数已获证据或已开始经济运行。
此核查不运行任何账户、不改原账、不使用分钟资料。固定未来池、历史可成交未知等旧研究边界仍在。
