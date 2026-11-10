from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,ast,math
O=Path(__file__).resolve().parent
x=pd.read_csv(O/'ACTUAL_FIRST_ENTRIES.csv');p=pd.read_csv(O/'FIXED_DATE_LEGAL_MOBILE.csv');e=pd.read_csv(O/'FIRST_SCORED_EVENTS_PER_REPRESENTED_ROOT.csv');pairs=pd.read_csv(O/'EXACT_LENGTH_SAME_DAY_SECTOR_PAIRS.csv')
# Recover calc definition without executing the analysis module or reading/account-running any original strategy.
tree=ast.parse((O/'analyze.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='calc');scope=dict(pd=pd,np=np,math=math);exec(compile(ast.Module(body=[node],type_ignores=[]),'calc_only','exec'),scope);calc=scope['calc']
def synthetic(extra_flat=0,price_scale=1.,amount_scale=1.):
 cs=[99.]*20+[101.,103.,100*math.exp(.05),100*math.exp(.01)]+[100*math.exp(.01)]*extra_flat+[102.]
 ix=pd.bdate_range('2020-01-01',periods=len(cs));f=pd.DataFrame(dict(close=np.array(cs)*price_scale,high=np.array([100.]*20+cs[20:])*price_scale,amount=np.ones(len(cs))*100*amount_scale,segment_id=0,i_target=[0]*20+[1]*(len(cs)-20)),index=ix)
 cp=pd.DataFrame(dict(receipt=[False]*(len(cs)-1)+[True]),index=ix)
 return f,cp,calc(f,cp)
f,cp,a=synthetic();_,_,b=synthetic(2);_,_,c=synthetic(price_scale=100,amount_scale=1000)
assert abs(a.Z.iloc[-1]-(-.07/.17))<1e-12
assert abs(b.Z.iloc[-1]-(.03/.27))<1e-12
assert abs(a.Z.iloc[-1]-c.Z.iloc[-1])<1e-12
pd.testing.assert_frame_equal(calc(f.iloc[:-1],cp.iloc[:-1]),a.iloc[:-1],check_exact=True,check_dtype=False)
synt=dict(passed=True,short_test_Z=float(a.Z.iloc[-1]),same_trough_plus_two_flat_days_Z=float(b.Z.iloc[-1]),price_and_amount_unit_invariance=True,prefix_invariance=True,interpretation='Two extra flat pullback days alone turn natural sign negative to positive; no extra price recovery or amount-rate change.')
(O/'SYNTHETIC_MECHANISM_CHECKS.json').write_text(json.dumps(synt,indent=2))
manifest={r['symbol']:r for r in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
known=x[x.Z_score_known].reset_index(drop=True);checks=[]
for n in np.linspace(0,len(known)-1,30,dtype=int):
 r=known.iloc[n];m=manifest[r.sid];path=next(s for s in m['source_sha256'] if s.endswith('/signal.parquet'))
 q=pd.read_parquet(path,columns=['close','high','amount']);facts=pd.read_parquet(m['refs']['facts']);q=q.reindex(facts.index)
 root=q.index.get_loc(pd.Timestamp(r.Z_root));base=q.iloc[root-20:root]
 B=float(base.high.max());ar=float(base.amount.median());up=q.loc[r.Z_breakday:r.Z_peakday];recovery=q.index.get_loc(pd.Timestamp(r.Z_recoveryday));peak=q.index.get_loc(pd.Timestamp(r.Z_peakday));test=q.iloc[peak+1:recovery]
 U=math.log(up.close.iloc[-1]/B);D=math.log(up.close.iloc[-1]/test.close.min());Vu=up.amount.sum()/ar;Vt=test.amount.sum()/ar;Z=(U*Vt-D*Vu)/(U*Vt+D*Vu)
 assert abs(Z-r.Z_Z)<1e-12 and abs(B-r.Z_B)<1e-10 and len(up)==r.Z_n_up and len(test)==r.Z_n_test
 assert pd.Timestamp(r.Z_peakday)<pd.Timestamp(r.Z_testday)<pd.Timestamp(r.Z_recoveryday)<=pd.Timestamp(r.signal_day)
 checks.append(dict(sid=r.sid,signal_day=r.signal_day,Z_direct=Z,error=abs(Z-r.Z_Z),passed=True))
pd.DataFrame(checks).to_csv(O/'DIRECT_FORMULA_CHECKS.csv',index=False)
# Explicitly correct left-truncated event naming, do not alter original raw export.
e['true_first_CP_in_root']=e.day.eq(e.firstcp);e.to_csv(O/'ROOT_EVENTS_WITH_FIRSTNESS.csv',index=False)
e[e.true_first_CP_in_root].to_csv(O/'TRUE_FIRST_SCORED_ROOT_EVENTS.csv',index=False)
pidx=p.set_index(['day','sid']);detail=[]
for r in pairs.itertuples():
 a=pidx.loc[(r.day,r.high)];b=pidx.loc[(r.day,r.low)];dt=a.Z_Z_time-b.Z_Z_time
 detail.append(dict(**r._asdict(),Z_time_delta=dt,amount_reverses_pair=bool(dt<0),same_total_wait=bool(r.delta_wait==0)))
pp=pd.DataFrame(detail).drop(columns='Index');pp.to_csv(O/'MATCHED_PAIR_AMOUNT_INCREMENT.csv',index=False)
rows=[]
for name,g in [('ALL_SCORED',known),('FIRST_Z_CP_AT_ACTUAL_ENTRY',known[known.Z_firstcp.eq(known.signal_day)]),('LATER_CP_REUSES_SAME_TEST',known[known.Z_firstcp.lt(known.signal_day)]),('ONE_ACTUAL_ENTRY_PER_I_ROOT',known.sort_values('signal_day').drop_duplicates(['sid','Z_root']))]:
 for label,h in [('ALL',g),('Z_POSITIVE',g[g.Z_Z>0]),('Z_NONPOSITIVE',g[g.Z_Z<=0])]:
  c=h[h.closed]
  rows.append(dict(cohort=name,split=label,N=len(h),closed=len(c),wins=int(c.round_pnl.gt(0).sum()),winrate=float(c.round_pnl.gt(0).mean()),mean_ret20=h.native_ret20.mean(),mean_ret60=h.native_ret60.mean(),big60=int(h.native_big60.sum())))
pd.DataFrame(rows).to_csv(O/'FRESHNESS_AND_ROOT_DEDUP.csv',index=False)
tail=[]
for name,g in [('ALL',x),('2024_924_TO_OCT31',x[x.signal_day.between('2024-09-24','2024-10-31')]),('2025H2',x[x.signal_day.between('2025-07-01','2025-12-31')]),('2026Q1',x[x.signal_day.between('2026-01-01','2026-03-31')])]:
 for state,h in g.groupby('Z_state'):
  tail.append(dict(period=name,state=state,N=len(h),big60=int(h.native_big60.sum()),known=int(h.Z_score_known.sum()),positive=int(h.Z_Z.gt(0).sum())))
pd.DataFrame(tail).to_csv(O/'MAJOR_PERIOD_STATE_COVERAGE.csv',index=False)
summary=dict(status='STOP_CURRENT_Z_PROMOTION_NO_NEW_ACCOUNT',actual_entries=len(x),native_CP_entries=int(x.Z_fresh_cp.sum()),score_known=len(known),score_positive=int(known.Z_Z.gt(0).sum()),fresh_first_Z_CP=int(known.Z_firstcp.eq(known.signal_day).sum()),later_CP_reuses_score=int(known.Z_firstcp.lt(known.signal_day).sum()),original_event_export1136_includes_left_truncated_repeats=int((~e.true_first_CP_in_root).sum()),true_first_root_events=int(e.true_first_CP_in_root.sum()),event_population_selected_by_eventually_actual_original_entries=True,fixed_opportunities=len(p),known_opportunities=int(p.Z_score_known.sum()),exact_length_pairs=len(pp),amount_reverses_pairs=int(pp.amount_reverses_pair.sum()),same_wait_pairs=int(pp.same_total_wait.sum()),direct_checks=len(checks),synthetic=synt,no_accounts=True,no_original_models=True,no_parameter_search=True)
(O/'FINAL_RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))

