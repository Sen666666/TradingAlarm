"""Narrow v2 correction using saved future-receipt tables only. Preserve all sealed v1 files."""
from pathlib import Path
import pandas as pd,json,hashlib
P=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/first_late_contraction_preflight_v1')
O=P/'CORRECTION_v2'
H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
manifest_path=src(P/'FINAL_OUTPUT_HASHES.json')
v1=json.loads(manifest_path.read_text())
assert len(v1)==24
assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in v1.items())
f=pd.read_csv(src(P/'SAME_ROOT_FUTURE_FRESH_RECEIPTS.csv'))
n=pd.read_csv(src(P/'STRICT_NEGATIVE_NEXT_OPPORTUNITY.csv'))
assert len(f)==215 and len(n)==54
assert not f.duplicated(['round_id','future_signal_day']).any()
assert f.same_original_root.eq(True).all() and f.fresh_frontier.eq(True).all()
assert f.nonnegative_gate.eq(f.peer_delta1_robust.ne('NEGATIVE')).all()
correct_fields=['nonnegative_gate','four_industry_known_true','old_conditional_close_feasible','old_conditional_open_feasible']
assert f[correct_fields].notna().all().all()
f['v1_all_saved_market_and_size_flags']=f.all_saved_market_and_size_flags
f['v2_PRICE_market_and_size_visible']=f[correct_fields].eq(True).all(axis=1)
f['v2_visibility_changed']=f.v1_all_saved_market_and_size_flags.ne(f.v2_PRICE_market_and_size_visible)
f['v2_route_boundary']='POTENTIAL_PRICE_APPLICATION_ONLY; LEGAL_AB_PRIORITY_AND_NEW_DYNAMIC_COMPETITION_NOT_REBUILT'
f['v2_stock_flags_role']='AB_OR_DESCRIPTIVE_ONLY_NOT_PRICE_GATE'
f['v2_PVR_known_role']='RANKING_DESCRIPTION_ONLY; UNKNOWN_PRICE_PVR_ALLOWED_AFTER_KNOWN'
first=f[f.v2_PRICE_market_and_size_visible].sort_values(['round_id','future_signal_day']).groupby('round_id',as_index=False).first()
take=['round_id','future_signal_day','peer_delta1_robust','next_common_open_day','old_conditional_close_feasible','old_conditional_open_feasible','original_stock_entry_flags_true','old_PVR_known','same_stock_AB_market_permit','original_AB_valid_close','old_AB_event_id','old_close_q','old_open_q','old_close_size_check','old_open_size_check','four_industry_known_true']
first=first[take].rename(columns={c:'v2_first_'+c for c in take if c!='round_id'})
out=n.merge(first,on='round_id',how='left',validate='one_to_one')
out['v2_first_date_changed']=out.first_market_size_visible_day.fillna('MISSING').ne(out.v2_first_future_signal_day.fillna('MISSING'))
out['v2_boundary']='SIGNAL_VISIBILITY_ONLY; NOT_NEW_SELECTION_ORDER_FILL_OR_RETURN'
f.to_csv(O/'FUTURE_RECEIPTS_PRICE_VISIBILITY_v2.csv',index=False)
out.to_csv(O/'STRICT_NEGATIVE_FIRST_PRICE_OPPORTUNITY_v2.csv',index=False)
changed=f[f.v2_visibility_changed].copy();changed.to_csv(O/'CHANGED_RECEIPT_FLAGS.csv',index=False)
c=out[out.v2_first_date_changed].copy();c.to_csv(O/'CHANGED_FIRST_OPPORTUNITIES.csv',index=False)
assert len(changed)==1 and changed.iloc[0].sid=='601288.SH' and changed.iloc[0].future_signal_day=='2024-12-05'
assert len(c)==1 and c.iloc[0].v2_first_future_signal_day=='2024-12-05' and c.iloc[0].v2_first_next_common_open_day=='2024-12-06'
summary=[]
for y,g in out.groupby('year'):
 z=f[f.year.eq(y)]
 summary.append(dict(year=int(y),strict_original_negative_rounds=len(g),v1_potential_rounds=int(g.first_market_size_visible_day.notna().sum()),v2_potential_rounds=int(g.v2_first_future_signal_day.notna().sum()),first_potential_date_changed=int(g.v2_first_date_changed.sum()),v1_visible_saved_receipts=int(z.v1_all_saved_market_and_size_flags.sum()),v2_visible_saved_receipts=int(z.v2_PRICE_market_and_size_visible.sum()),receipt_flags_changed=int(z.v2_visibility_changed.sum()),saved_future_PVR_unknown=int(z.old_PVR_known.ne(True).sum())))
dump('SUMMARY.json',summary)
readout="""# 窄正确性更正 v2：PRICE未来机会口径

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
"""
(O/'READOUT.md').write_text(readout)
assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in v1.items())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in H.items())
dump('SOURCE_HASHES.json',H)
dump('QA.json',dict(v1_sealed_files=24,v1_sealed_files_unchanged=True,v1_manifest_unchanged=True,input_sources_unchanged=True,future_saved_receipts=215,original_negative_rounds=54,changed_receipts=1,changed_first_opportunities=1,new_trace_reads=0,new_market_reads=0,economic_runs=0,consumer_imports=0,parameter_searches=0,AB_route_and_dynamic_queue_not_rebuilt=True,PRICE_stock_E0_I_i_buy_gate=False,PRICE_PVR_known_gate=False))
dump('OUTPUT_HASHES.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('v1 sealed 24 files unchanged; v2 correction complete.')
