"""Reuse audited Top3 accounting; append frozen-attention diagnostics only."""
import attention as A
import sys,importlib.util,json,gzip,time,collections,copy
import pandas as pd,numpy as np
M,T,X,O=A.M,A.T,A.X,A.O
def main():
 t=time.monotonic();sys.modules['top3']=T
 s=importlib.util.spec_from_file_location('attention_reused_account_analysis',A.HT/'analyze.py');old=importlib.util.module_from_spec(s);sys.modules[s.name]=old;s.loader.exec_module(old);old.O=O;old.main()
 out=O/'analysis';pair=M.read(out/'SUMMARY.json');h=copy.deepcopy(next(r for r in M.read(A.HT/'analysis/SUMMARY.json') if r['account']=='T3'));h['account']='H1_TOP3';n=copy.deepcopy(pair[1]);n['account']='ATT_TOP3';summaries=[pair[0],h,n];M.save(out/'SUMMARY_3.json',summaries);pd.DataFrame(M.N.encoded(summaries)).to_csv(out/'SUMMARY_3.csv',index=False)
 origins=M.read(out/'ORIGIN_CONTRIBUTIONS.json');origins=[dict(r,account='ATT_TOP3') if r['account']=='T3' else r for r in origins]+[dict(r,account='H1_TOP3') for r in M.read(A.HT/'analysis/ORIGIN_CONTRIBUTIONS.json') if r['account']=='T3'];M.save(out/'ORIGIN_CONTRIBUTIONS_3.json',origins);pd.DataFrame(origins).to_csv(out/'ORIGIN_CONTRIBUTIONS_3.csv',index=False)
 matrix=pd.read_parquet(M.F).set_index(['day','sector']);meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');names={v['sector_id']:v['industry'] for v in meta.values()};diagnostics=[];coverage=[]
 for policy,root in [('H1_TOP3',A.HT),('ATT_TOP3',O)]:
  targets=M.read(root/'TARGETS.json');rr=[]
  for r in targets:
   for sec in r['targets']:
    q=matrix.loc[(r['day'],sec)];z=dict(policy=policy,day=r['day'],sector=sec,industry=names[sec],R21=float(q.R21),R21_nonpositive=bool(q.R21<=0),attention=float(q.attention_ratio),attention_le1=bool(q.attention_ratio<=1),effective_members=int(q.attention_members),snapshot_members=int(q.member_count),member_coverage=float(q.attention_members/q.member_count),effective_lt5=bool(q.attention_members<5),snapshot_lt5=bool(q.member_count<5),subpool_complete26_members=int(q.denominator_complete_window_members));diagnostics.append(z);rr.append(z)
  coverage.append(dict(policy=policy,target_industry_days=len(rr),R21_nonpositive_industry_days=sum(r['R21_nonpositive'] for r in rr),attention_le1_target_days=sum(r['attention_le1'] for r in rr),effective_member_min=min(r['effective_members'] for r in rr),effective_member_median=float(np.median([r['effective_members'] for r in rr])),effective_member_max=max(r['effective_members'] for r in rr),snapshot_member_min=min(r['snapshot_members'] for r in rr),snapshot_member_max=max(r['snapshot_members'] for r in rr),effective_lt5_days=sum(r['effective_lt5'] for r in rr),snapshot_lt5_days=sum(r['snapshot_lt5'] for r in rr),coverage_min=min(r['member_coverage'] for r in rr),coverage_median=float(np.median([r['member_coverage'] for r in rr])),subpool_complete26_members_min=min(r['subpool_complete26_members'] for r in rr),subpool_complete26_members_max=max(r['subpool_complete26_members'] for r in rr)))
 # Actual new economic cycles, not duplicated fill profits. Groups are based
 # solely on original signal-day sector R21; no policy gate is added.
 ob=T.obj(O/'results/T3.json.gz');buys={(tr['security_id'],tr['at']):tr for tr in ob['trades'] if tr['side']=='buy'};cycles=M.read(out/'T3_CYCLES.json');categorized=[]
 for c in cycles:
  if c['entry_at'][:10]<='2025-09-30':continue
  tr=buys[c['symbol'],c['entry_at']];day=tr['signal_at'][:10]
  if day<='2025-09-30':continue
  q=matrix.loc[(day,meta[c['symbol']]['sector_id'])];cat='nonpositive' if np.isfinite(q.R21) and q.R21<=0 else 'positive' if np.isfinite(q.R21) else 'unknown'
  categorized.append(dict(sid=c['symbol'],name=c['name'],industry=c['industry'],decision=day,entry=c['entry_at'],exit=c['exit_at'],closed=c['closed'],R21=float(q.R21),category=cat,buy_cost=float(c['buy_gross'])+float(c['buy_fees']),net=float(c['Q4_net_contribution']),effective_members=int(q.attention_members),snapshot_members=int(q.member_count)))
 split=[]
 for cat in ['nonpositive','positive','unknown']:
  cc=[r for r in categorized if r['category']==cat];split.append(dict(category=cat,cycles=len(cc),buy_cost=sum(r['buy_cost'] for r in cc),closed_cycles=sum(r['closed'] for r in cc),closed_net=sum(r['net'] for r in cc if r['closed']),open_cycles=sum(not r['closed'] for r in cc),open_marked_net=sum(r['net'] for r in cc if not r['closed'])))
 # Weekly funding includes zero-activity weeks, preserving the full Q4.
 flows=M.read(out/'ACTUAL_BUY_USAGE.json');weeks=[r['week'] for r in M.read(out/'WEEKLY_TARGETS.json')];weekly=[]
 for policy in ['RAW','T3']:
  fresh=[r for r in flows if r['account']==policy and not r['transition']]
  for week in weeks:
   ff=[r for r in fresh if str(pd.Period(r['decision'],'W-FRI'))==week];weekly.append(dict(policy='ATT_TOP3' if policy=='T3' else policy,week=week,buy_fills=len(ff),industries=len({r['sector'] for r in ff}),industry_names=sorted({r['industry'] for r in ff}),cash_cost=sum(float(r['cash_cost']) for r in ff)))
 conc=M.read(out/'NEW_ENTRY_CONCENTRATION.json');hconc=next(r for r in M.read(A.HT/'analysis/NEW_ENTRY_CONCENTRATION.json') if r['account']=='T3');concs=[dict(r,account='ATT_TOP3') if r['account']=='T3' else r for r in conc]+[dict(hconc,account='H1_TOP3')]
 for name,rs in [('TARGET_ATTENTION_DIAGNOSTICS',diagnostics),('TARGET_MEMBER_COVERAGE',coverage),('R21_NEW_CYCLE_SPLIT',split),('R21_NEW_CYCLES',categorized),('WEEKLY_ENTRY_FUNDING',weekly),('NEW_ENTRY_CONCENTRATION_3',concs)]:M.save(out/(name+'.json'),rs);pd.DataFrame(rs).to_csv(out/(name+'.csv'),index=False)
 v=M.read(out/'VERIFICATION.json');v['attention_diagnostics_read_only_no_policy_changes']=True;v['three_arm_comparison_uses_two_old_results']=True;v['total_read_only_analysis_seconds']=time.monotonic()-t;M.save(out/'VERIFICATION.json',v)
 print('SUMMARY3',[(r['account'],r['Q4_net_return'],r['Q4_max_drawdown']) for r in summaries],flush=True);print('TARGET_COVERAGE',json.dumps(coverage,ensure_ascii=False),flush=True);print('R21_CYCLES',json.dumps(split,ensure_ascii=False),flush=True);print('ANALYSIS_SECONDS',time.monotonic()-t,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
