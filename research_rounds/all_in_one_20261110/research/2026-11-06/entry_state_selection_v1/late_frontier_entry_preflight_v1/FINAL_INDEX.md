# 最终交付索引

结论：唯一late首探候选的静态事实预检完成，独审PASS；未跑经济、未算过滤收益。最终安全解释仅用unknown_hardening_v2，v1及其bool(NaN)漏洞复现保留。

原PRICE消费者只有原行业四真，并没有行业Stage active门。本候选新增要求分两部分：复用既有行业Stage active机制，再要求当前accepted授权确认严格晚于stockroot.birth。共同原BUY中前者作用47/1779（2022）、113/1083（2024）；严格时间关系的纯新增163/1779=9.16%、31/1083=2.86%。后者含同生日86/16，不全是出生前陈旧票。

按阅读顺序：
1. READOUT.md：全分母、root/birth/late/parent、source与固定正反例解释。
2. RESPONSIBILITY_FOUR_GROUP_COUNTS.csv：16个全/共同/市场票/原close-pass/登记/原BUY分母及四职责计数，无金额。
3. MECHANICAL_AND_CLOCK_APPENDIX.md：纯新增同日/早于时钟分解、两个不看盈亏的机械例。
4. unknown_hardening_v2/FIXED_CASE_PREFLIGHT_FINAL_STRICT.csv：最终固定案例，明确实际parent未知与假设无parent信号条件。
5. unknown_hardening_v2/MARKET_STRICT_LABELS.csv、REGISTERED_STRICT_LABELS.csv：37,456/3,621逐行安全标签。与v1已知标签全部exact。
6. REGISTERED_ENTRY_BASE_FACTS.csv、MARKET_RECEIPT_BASE_FACTS.csv：未套新式的完整基事实；REGISTERED_ENTRY_PREFLIGHT.csv、MARKET_RECEIPT_PREFLIGHT.csv保存完整源字段及历史已知标签。其v1代码不能作为UNKNOWN-safe实现复用。
7. ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv：25,227全史原行业CP1票、形成/确认时间、accepted、source及Stage身份对应。
8. INDEPENDENT_AUDIT_FINAL.json：独审37,456/3,621三列exact、20独立边界测试；v2另140合成PASS，所有hash一致。
9. FINAL_DELIVERY_SEAL.json：截至最终交付的全部文件SHA256及源hash复核。

CONTRACT.md为唯一冻结式。出生日原资格保留，不跳过原四真/AB/PVR/执行责任；已有PROBE parent不读新门；真实zero/partial/ACK证据未知；窗前root不推断窗前实际参与。未知经济总损益不填0。所有金额只描述旧冻结路径，不是此候选的新收益。此交付不是执行consumer、上线批准或实时可成交证明。
