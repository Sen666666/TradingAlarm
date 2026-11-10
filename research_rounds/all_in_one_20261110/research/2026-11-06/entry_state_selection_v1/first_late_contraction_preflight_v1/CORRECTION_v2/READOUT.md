# 窄正确性更正 v2：PRICE未来机会口径

仅从v1保存的215张SAME_ROOT_FUTURE_FRESH_RECEIPTS和54行首次机会表重判，不读新trace、行情或执行consumer。v1脚本、表、READOUT与封存24文件全部保留未改；本附录对下述错误解释具有优先权。

## 撤回的错误

v1 audit_saved.py将股票old_e0_target、old_i_target、old_i_buy合成的original_stock_entry_flags_true，以及old_PVR_known，误加入独立PRICE初仓未来机会门。独立PRICE不以这三个股票flags作为初仓准入；PRICE PVR未知也允许排在已知者之后。前者仅AB/描述旁列，后者仅排序描述，不能用于延迟或抹除PRICE潜在申请。

更正后的静态可见条件仅为：
nonnegative_gate AND 原fourIndustry为真 AND 保存的PRICE条件close sizing可见 AND 保存的PRICE条件next OPEN sizing可见。

仍必须是同原root后来真实fresh frontier。该式只描述潜在PRICE申请，原AB合法优先仍可改变路由；没有重建新臂空仓时AB接管、行业TOP2队列、资金/仓位竞争或实际成交。

## 唯一受影响首日

农业银行601288.SH：
- v1错误：首次完整机会2024-12-06，条件OPEN2024-12-09。
- v2正确：首次潜在PRICE申请2024-12-05，条件OPEN2024-12-06。
- 12-05为POSITIVE，fourIndustry和保存的PRICE close/open条件均真；原stockflags为false不应阻止PRICE。
- 因此撤回v1 READOUT“12-05 stock资格不全，12-06才完整”的PRICE延迟解释。

## 不变与变化

- 窗口首次且本窗出生的原NEG54例及其目标分组、独立CORE/FULL、出生/parent核验均不变。
- 同根首张Δ非NEG仍2022 9/12、2024 35/42。
- 合正确PRICE可见条件的潜在回合仍9/12、35/42，仅农业银行首日提前一张票。
- 2022合条件保存fresh票保持35；2024从141增至142，215张票中恰有1张标记改变。
- 215张保存票PVR均已知，因此移除PVR-known错误门在本样本没有数值影响，但规则逻辑已纠正。不能据此把未知PVR继续当作PRICE否决门。
- 正常退出后新root独立层、born旁路和原未来新root路径不受影响。过去买过股票仍只描述分层，不构成永久准入标记。

## 安全结论

仍只是原保存市场票的静态潜在新申请，绝非新策略选择、订单、成交或收益。UNKNOWN/FLAT不作负，旧票不复活；原born旁路及已有parent责任不改。旧组盈亏未用于筛票。没有经济、全生命周期重跑、参数搜索、新行情、源文件或v1产物修改。保留原窄预检结论，不据此宣称策略已改善。

文件：
- FUTURE_RECEIPTS_PRICE_VISIBILITY_v2.csv：215张保存票的正确PRICE可见标记及原旁列。
- STRICT_NEGATIVE_FIRST_PRICE_OPPORTUNITY_v2.csv：54例正确首次潜在日期，保留v1日期对照。
- CHANGED_RECEIPT_FLAGS.csv / CHANGED_FIRST_OPPORTUNITIES.csv：唯一变化。
- SUMMARY.json、QA.json、SOURCE_HASHES.json、OUTPUT_HASHES.json：复核与封存。

## 旧研究脚本不可作为consumer

audit_saved.py、supplement_paths.py、audit_reentry_layer.py均是保存事实的旧研究脚本，不是待执行的策略consumer，也不是生产准入合同。旧脚本中EXEMPT_PRIOR_WINDOW_BUY、first-window检查等范围标签属于先前已撤回的全股/永久豁免解释；最终root-local研究合同不采用这些分支，不得复制成执行规则。应按当前root是否已经建立PROBE parent区分责任；同股此前BUY仅用于独立描述分层。

当前固定早例全部属于born旁路或非NEG，不会落入这些旧范围分支，因此该死分支不影响已报固定早例结果，本次不重算研究。v2真正的PRICE未来机会判定已在correct_saved_price_visibility.py中仅使用nonnegative_gate、fourIndustry、PRICE条件close/open sizing四项，完全移除stockflags与PVR-known门，二者仅保留旁列。
