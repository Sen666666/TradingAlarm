H2完整账户结果比较准备：尚未执行。

BASELINE复用trend_exit_controls_v1/runs/BASELINE两本原No60已冷复现账户；
R_ONLY/P_ONLY/JOINT只读本H2 runs的新完成结果。没有账户/执行器导入或运行。
默认需全部8个existing paths的DONE/TIMING/pair与独审ACCOUNT_AUDIT齐全。
--available仅在父通知后供一次扫描已完成且已独审的pairs，不循环轮询、不重放账户。

复用封版compare_accounts.py的analyze_run、partial-layer basis侧表、原生每日mark与
strict realized/open unrealized/AR/NAV核对、matched/full-fixed-tail算法；原helper文件
不改、不开账户、不向其目录写pycache。仅注入路径/固定period，供其调用只读EMA兼容
视图以满足旧无关诊断字段，随即删除旧entry-tool字段并用H2真实context取代。
绝不会把该兼容视图当成R_ONLY/JOINT触发条件，真实授权日志与provider另核。

固定32行=4臂×8period：连续2022—24、2022、Dec2022、2023、2024、2024-09-24起、
2024-10-08后、strong。年/月起点都用前一实际CLOSE/NAV，不重置钱账。
输出绝对NAV/净财富/收益、period DD和全账户峰值DD、暴露/现金、real/open/AR、
费用/周转/成交及ACT变化。若部分权益/basis未知或非零zero-unit writeoff不被旧helper
覆盖，报错并保留分析，不以unknown=0拼出PASS；可接独审精确侧表后另开分析目录。

每臂自己的Nov30旧库存+Dec实际first/add/真flat reentry按当月财富拆分，非终局PNL；
capitaltime采用原生持层成本/市值×CLOSE观察数，prior CLOSE和current CLOSE分开。
部分出售跨界使用成熟partial basis时间侧表。每月财富/组件/原生inventory桥要核同。

原BASE87与122全员固定full entrykey单独对应：sid+role+CP receipt+decision_at+actualentry。
同键曾参与、Nov30还持有、当月贡献分别记录；原键缺席不等于直接H2拒绝或从未持有该股。
只有真实role-log在相同decision/sid/mobile/CP明确拒绝时，才标direct guard denial。
有原键也不假装same-hold counterfactual；各臂自身历史/数量/资金/ACT/新路径均不同。

固定原83/94全员保留及旧45/67当前基线对应；全路径匹配/缺席/新key、CORE/mobile真实
金额均列。新增key不是新股票，固定尾部少参与不直接等于误卖或可回收收益。
供销/众生/科传/深深房分别保真实entries/campaigns、Dec组件及截至Dec的全部授权日志。
完整lifecycle净额可以在Dec以后形成，明确不得用来替代Dec财富。

H2动作核查：被拒mobile不得进入原pending；已有mobile新增退出目标中CORE=0；
保留每个真实sell.part理由与原order clock，原CP先锁/部分卖出的层不重归H2。
UNKNOWN分别计mode readiness，未施加覆盖不是趋势已修复。CORE规则不直接变并不保证
后续实际CORE数量/入场与BASE相同。H2退mobile后新CP可再入时，区分全股flat reentry与
仍有CORE持仓的add，核其CP为新receipt，不自动买回/续旧receipt。

待父DONE通知后：
/Users/bytedance/.cache/uv/archive-v0/BCk79KzaN8dGdkNqEjF-9/bin/python \
 entry_quality/dec2022_authorization_v1/account_comparison/compare_h2_accounts.py

默认results_v1，拒绝覆盖；阶段扫描须--available --out 新目录。输出schema见SCHEMA.json。
当前只做AST与不启动main的导入检查，不读取新pairs结果。
