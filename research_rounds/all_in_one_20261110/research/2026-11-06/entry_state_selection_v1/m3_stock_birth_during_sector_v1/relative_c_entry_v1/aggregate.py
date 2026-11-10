"""Postprocess frozen C preflight only; no economic simulation or return labels."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;E=O.parent;BASE=E/'relative_priority_v1/baseline'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'SUMMARY.json').exists()
qa=[read(O/f'QA_{i}.json') for i in range(8)]
assert sum(x['stocks'] for x in qa)==1627 and sum(x['old_AB_checks'] for x in qa)==20445
inputs=[O/f'{stem}_{i}.{ext}' for i in range(8) for stem,ext in [('CANDIDATES','csv'),('MARK_TRANSITIONS','csv'),('FIXED_DAILY','csv'),('DAILY_FEATURES','parquet'),('SOURCE_QA','csv'),('QA','json')]]
inputs+=[O/'FREEZE.json',O/'FIXED_CASE_DEFINITIONS.csv',O/'aggregate.py']
save('POSTPROCESS_SEAL.json',{'created_utc':str(pd.Timestamp.now(tz='UTC')),'before_aggregate_outputs':True,'hashes':{str(p):sha(p) for p in inputs},'no_new_returns':True})
c=pd.concat([pd.read_csv(O/f'CANDIDATES_{i}.csv',parse_dates=['day'],dtype={'window':str}) for i in range(8)],ignore_index=True)
m=pd.concat([pd.read_csv(O/f'MARK_TRANSITIONS_{i}.csv',parse_dates=['day'],dtype={'window':str}) for i in range(8)],ignore_index=True)
fd=pd.concat([pd.read_csv(O/f'FIXED_DAILY_{i}.csv',parse_dates=['day'],dtype={'window':str}) for i in range(8)],ignore_index=True)
f=pd.concat([pd.read_parquet(O/f'DAILY_FEATURES_{i}.parquet') for i in range(8)],ignore_index=True)
d=pd.read_csv(BASE/'DECISIONS.csv',parse_dates=['day'],dtype={'window':str})
assert len(c)==2242 and not c.duplicated(['window','day','sid']).any()
assert not c.old_AB_same_day.any()
c['close_feasible']=c.close_check.eq('PASS')
c['C_queue_eligible']=c.unconsumed_marker&c.current_FLAT&c.PVR_known&c.close_feasible
c['C_remaining_slot_eligible']=c.C_queue_eligible&c.C_slots.gt(0)
c['C_rank']=np.nan;c['shadow_C_selected']=False
for key,g in c[c.C_remaining_slot_eligible].groupby(['window','day','sector']):
 ordered=g.sort_values(['PVR_score','sid'],ascending=[False,True],kind='stable')
 slots=int(ordered.C_slots.iloc[0]);assert ordered.C_slots.eq(slots).all()
 c.loc[ordered.index,'C_rank']=np.arange(1,len(ordered)+1)
 c.loc[ordered.index[:slots],'shadow_C_selected']=True
assert (c[c.shadow_C_selected].groupby(['window','day','sector']).size()+c[c.shadow_C_selected].groupby(['window','day','sector']).AB_awards.first()).le(2).all()
c['known_open_proxy']=c.next_open_status.eq('CONDITIONAL_OPEN_PROXY')
c['shadow_C_selected_known_open']=c.shadow_C_selected&c.known_open_proxy
c['shadow_only_warning']='Baseline never executes C. Repeated shadow awards are not ABC entries.'
ab_awards=d[d.selected.eq(True)].groupby(['window','day','sector']).apply(lambda g:'; '.join(g.sid+' '+g['name']),include_groups=False).to_dict()
c['unchanged_AB_award_stocks']=[ab_awards.get((r.window,r.day,r.sector),'') for r in c.itertuples()]
def reason(r):
 if not r.same_I_prior_AB_loss:return 'NO_PRIOR_LEGAL_AB_LOSS_IN_SAME_I'
 if not r.unconsumed_marker:return 'MARKER_CLEARED_OR_NOT_ESTABLISHED'
 if not r.current_FLAT:return 'BASELINE_'+r.baseline_state
 if not r.PVR_known:return 'PVR_UNKNOWN_TODAY'
 if not r.close_feasible:return str(r.close_check)
 if r.C_slots==0:return 'AB_USED_BOTH_SLOTS'
 if not r.shadow_C_selected:return 'C_PVR_NOT_WITHIN_REMAINING_SLOTS'
 return str(r.next_open_status)
c['first_block_or_proxy']=c.apply(reason,axis=1)
summary=[];den=[]
for w,g in c.groupby('window',sort=False):
 counts=dict(window=w,broad_persistent_fresh=len(g),same_I_prior_AB_loss=int(g.same_I_prior_AB_loss.sum()),unconsumed_marker=int(g.unconsumed_marker.sum()),current_FLAT_with_marker=int((g.unconsumed_marker&g.current_FLAT).sum()),PVR_known_after_marker=int((g.unconsumed_marker&g.current_FLAT&g.PVR_known).sum()),close_feasible=int(g.C_queue_eligible.sum()),AB_remaining_slot=int(g.C_remaining_slot_eligible.sum()),C_PVR_shadow_awarded=int(g.shadow_C_selected.sum()),shadow_awarded_unique_stocks=int(g[g.shadow_C_selected].sid.nunique()),next_open_known_proxy=int(g.shadow_C_selected_known_open.sum()),next_open_NOFILL=int((g.shadow_C_selected&g.next_open_status.fillna('').str.contains('NOFILL')).sum()),next_open_UNKNOWN=int((g.shadow_C_selected&g.next_open_status.fillna('').str.contains('UNKNOWN')).sum()),next_open_pending_end=int((g.shadow_C_selected&g.next_open_status.eq('BUY_PENDING_AT_DATA_END')).sum()),direct_AB_event_conflicts=int(g.old_AB_same_day.sum()))
 summary.append(counts)
 for stage,mask in [('ALL_PERSISTENT',pd.Series(True,index=g.index)),('SAME_I_PRIOR_LOSS',g.same_I_prior_AB_loss),('VALID_MARKER_FLAT',g.unconsumed_marker&g.current_FLAT),('ORIGINAL_CLOSE_PASS',g.C_queue_eligible)]:
  for slots in [0,1,2]:den.append(dict(window=w,stage=stage,AB_awards=slots,C_slots=2-slots,count=int((mask&g.AB_awards.eq(slots)).sum()),stage_total=int(mask.sum())))
# Later A/B conflicts are risk footprints, not a new held-position result.
fx=f.set_index(['window','sid','day']);risk=[]
for r in c[c.shadow_C_selected_known_open].itertuples():
 future=d[d.window.eq(r.window)&d.sid.eq(r.sid)&d.day.gt(r.day)]
 for z in future.itertuples():
  ep=fx.loc[(r.window,r.sid,z.day),'I_continuity_epoch']
  same=pd.notna(ep) and ep==r.I_continuity_epoch
  if same:risk.append(dict(window=r.window,sid=r.sid,name=r.name,C_signal_day=r.day,C_proxy_entry_day=r.next_common_day,original_AB_day=z.day,original_AB_event_id=z.event_id,original_AB_decision=z.decision,original_AB_selected=z.selected,same_I_episode=True,status='POTENTIAL_HOLDING_OR_UNKNOWN_BLOCK_NOT_ECONOMIC_RESULT'))
risk=pd.DataFrame(risk)
if len(risk):risk.to_csv(O/'LATER_AB_CONFLICT_RISK.csv',index=False)
else:pd.DataFrame(columns=['window','sid','C_signal_day','original_AB_event_id']).to_csv(O/'LATER_AB_CONFLICT_RISK.csv',index=False)
cases=pd.read_csv(O/'FIXED_CASE_DEFINITIONS.csv',dtype={'window':str});caseout=[]
for rr in cases.to_dict('records'):
 w,s=rr['window'],rr['sid'];g=c[c.window.eq(w)&c.sid.eq(s)].sort_values('day');ff=fd[fd.window.eq(w)&fd.sid.eq(s)]
 z=dict(rr,baseline_days_visible=len(ff),broad_persistent_fresh=len(g),same_I_prior_loss=int(g.same_I_prior_AB_loss.sum()),valid_marker=int(g.unconsumed_marker.sum()),close_feasible=int(g.C_queue_eligible.sum()),shadow_C_awards=int(g.shadow_C_selected.sum()),known_open_shadow_C=int(g.shadow_C_selected_known_open.sum()),first_broad_fresh=g.day.min() if len(g) else None,first_shadow_C=g[g.shadow_C_selected].day.min(),first_known_open_shadow_C=g[g.shadow_C_selected_known_open].day.min(),all_block_reasons=json.dumps(g.first_block_or_proxy.value_counts().to_dict(),ensure_ascii=False))
 if pd.notna(rr.get('baseline_later_entry_day')):
  target=pd.Timestamp(rr['baseline_later_entry_day']);missed=rr.get('missed_early_AB_day')
  if pd.isna(missed):missed=rr.get('priority_new_signal_day')
  lo=pd.Timestamp(missed) if pd.notna(missed) else pd.Timestamp('1900-01-01')
  interval=g[g.day.gt(lo)&pd.to_datetime(g.get('next_common_day'),errors='coerce').lt(target)]
  hit=interval[interval.shadow_C_selected_known_open]
  z.update(target_interval_after=lo if lo.year>1900 else None,target_interval_before=target,first_targeted_C_signal=hit.day.min(),first_targeted_C_open=hit.next_common_day.min() if len(hit) else None,targeted_C_count=len(hit),target_interval_persistent_count=len(interval),target_interval_block_reasons=json.dumps(interval.first_block_or_proxy.value_counts().to_dict(),ensure_ascii=False),target_comparison='Diagnostic only; old entry dates are not C eligibility inputs.')
 caseout.append(z)
casesout=pd.DataFrame(caseout);casesout.to_csv(O/'FIXED_CASE_STATUS.csv',index=False)
# Predeclared lexical examples: no profit-based choices.
examples=[]
for w in ['2022','2024_924','2026H1_SEMI']:
 g=c[c.window.eq(w)].sort_values(['day','sid'])
 for typ,mask in [('C_PASS_KNOWN_OPEN',g.shadow_C_selected_known_open),('C_CLOSE_REJECT',g.unconsumed_marker&g.current_FLAT&g.PVR_known&~g.close_feasible),('AB_FULL',g.C_queue_eligible&g.AB_awards.eq(2))]:
  z=g[mask];examples.append(dict(window=w,example_type=typ,exists=bool(len(z)),**(z.iloc[0].to_dict() if len(z) else {})))
 z=m[m.window.eq(w)&m.reason.isin(['QUALIFICATION_UNKNOWN','EXECUTION_UNKNOWN'])].sort_values(['day','sid'])
 examples.append(dict(window=w,example_type='UNKNOWN_CLEARED_MARK',exists=bool(len(z)),**(z.iloc[0].to_dict() if len(z) else {})))
pd.DataFrame(examples).to_csv(O/'PREDECLARED_EXAMPLES.csv',index=False)
c.sort_values(['window','day','sector','sid']).to_csv(O/'CANDIDATE_PREFLIGHT.csv',index=False)
m.sort_values(['window','day','sid']).to_csv(O/'MARK_TRANSITIONS.csv',index=False)
fd.sort_values(['window','sid','day']).to_csv(O/'FIXED_DAILY.csv',index=False)
pd.DataFrame(summary).to_csv(O/'FUNNEL.csv',index=False)
pd.DataFrame(den).to_csv(O/'AB_SAME_DAY_SLOT_DENOMINATORS.csv',index=False)
c.groupby(['window','first_block_or_proxy']).size().rename('count').reset_index().to_csv(O/'BLOCK_REASONS.csv',index=False)
extra={'windows':summary,'original_AB_rows':len(d),'original_AB_same_day_selected_decisions_unchanged':True,'clock_stocks':1627,'full_clock_warm_days':4595,'engine_days':1085,'M_warm_and_main_days':1088,'market_feature_rows':len(f),'fixed_cases':len(casesout),'2022_fixed20_target_hits':int(casesout[casesout.group.eq('2022_FIXED_20_EARLY')].targeted_C_count.gt(0).sum()),'2022_fixed20_denominator':20,'baseline_AB_state_reconstruction_exact':True,'baseline_original_close_checks_exact':True,'all_original_AB_clock_features_exact':True,'all_previous_nonzero_clock_events_exact':True,'no_new_economic_run':True,'future_conflicts':risk.groupby('window').size().to_dict() if len(risk) else {},'future_original_selected_conflicts':risk[risk.original_AB_selected].groupby('window').size().to_dict() if len(risk) else {},'shadow_repeated_awards':c[c.shadow_C_selected].groupby(['window','sid']).size().sub(1).clip(lower=0).groupby('window').sum().to_dict()}
save('SUMMARY.json',extra)
lines=['# C入口冻结预检','', '仅基线真实状态的影子候选/配额诊断，不执行C、不产生新收益。多个同股影子C不能相加当成ABC入场；真实第一次C成交会清资格并改变后续状态。','',pd.DataFrame(summary).to_string(index=False),'','2022固定20早例，在错过原较早A/B后、旧臂后来入场前，出现获剩余名额且次开已知代理C的病例：'+str(extra['2022_fixed20_target_hits'])+'/20。','', 'AB直接同日事件冲突为0；但较早C持有/UNKNOWN可阻断未来AB，详见LATER_AB_CONFLICT_RISK.csv。此为风险足迹，不是新臂实际阻断结果。','', '模型和成本完全冻结：原interval relative时钟；原close、含费24000预算、3000风险、原20正成交量观察容量、5bp双向滑点、原dated lot/fees。行业AB先处理，C只分剩余，不看次开结果替补。','', '每窗口AB股票集合对C定义闭合，因为窗口外标记不继承且必须窗口内合法AB落选造标。1627并集之外82只无此必要条件，不是漏算符合定义的C；原NON-PIT和历史交易许可限制仍存在。','', '文件：FUNNEL.csv、CANDIDATE_PREFLIGHT.csv、FIXED_CASE_STATUS.csv、FIXED_DAILY.csv、AB_SAME_DAY_SLOT_DENOMINATORS.csv、MARK_TRANSITIONS.csv、PREDECLARED_EXAMPLES.csv。DAILY_FEATURES_0..7.parquet保存全股票窗内日级市场知识状态，FREEZE.json与POSTPROCESS_SEAL.json固定输入。','', '经济ABC未运行，须独审通过并再次明确授权。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
outs=[p for p in O.iterdir() if p.is_file() and p.name not in ['FINAL_OUTPUT_HASHES.json'] and p.suffix in ['.csv','.json','.md','.parquet','.py']]
save('FINAL_OUTPUT_HASHES.json',{p.name:sha(p) for p in outs})
print(pd.DataFrame(summary).to_string(index=False));print('FIXED20',extra['2022_fixed20_target_hits'],'/20');print('RISK',extra['future_conflicts'],extra['future_original_selected_conflicts'])
