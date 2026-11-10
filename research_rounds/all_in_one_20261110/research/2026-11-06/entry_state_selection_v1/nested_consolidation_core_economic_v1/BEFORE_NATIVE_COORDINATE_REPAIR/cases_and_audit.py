from pathlib import Path
import json,importlib.util,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen_core',O/'run.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
s.cal=pd.DatetimeIndex(np.load(s.H,allow_pickle=False)['dates'])
assert not (O/'CASE_RUN_ONCE.json').exists()
s.save('CASE_RUN_ONCE.json',dict(time_utc=str(pd.Timestamp.now(tz='UTC')),timing='After main three-arm summary. Fixed six dates predate economics; no additional selection/thresholds. Same frozen engine; these cases were originally requested and are excluded from all main cohort totals.',initialization='For each sid initial FLAT at earliest of its fixed candidate dates, candidate signals permitted through last fixed candidate date (600396 Oct25 and28 share one continuing root). Separate Jiangfeng December2025 window starts Dec1 FLAT and allows full month births. CONTROL/LOCAL/UNION same fees/exits. This is artificial isolated mechanism initialization, not proof union would be flat in real system.',script_sha256=s.sha(__file__),engine_sha256=s.sha(O/'run.py')))
events=pd.read_csv(s.P/'ALL_FIXED_WINDOW_CANDIDATE_FACTS.csv').drop_duplicates(['sid','day']);manifest={x['symbol']:x for x in s.read(s.M)}
for sid,g in events.groupby('sid'):
 m=manifest[sid];raw=pd.read_parquet(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')));f=pd.read_parquet(m['refs']['facts']);p=raw.reindex(s.cal)
 windows=[('FIXED_CASE_'+sid,g.day.min(),g.day.max())]
 if sid=='300666.SZ':windows.append(('JIANGFENG_DEC2025','2025-12-01','2025-12-31'))
 for win,start,finish in windows:
  fmap={k:s.features(p,k) for k in np.flatnonzero((s.cal>=pd.Timestamp(start))&(s.cal<=pd.Timestamp(finish)))}
  for arm in ['CONTROL','LOCAL','UNION']:s.run_stock(sid,win,start,finish,arm,p,f,fmap)
pd.DataFrame(s.rounds).to_csv(O/'CASE_MECHANISM_ROUNDS.csv',index=False);pd.DataFrame(s.paths).to_csv(O/'CASE_MECHANISM_DAILY_PATHS.csv',index=False);pd.DataFrame(s.coverage).to_csv(O/'CASE_MECHANISM_COVERAGE.csv',index=False)
z=pd.read_csv(O/'ROUNDS.csv');paths=pd.read_csv(O/'DAILY_ROOT_PATHS.csv');paired=pd.read_csv(O/'PAIRED_STOCK_DIFFERENCES.csv');cov=pd.read_csv(O/'COVERAGE.csv')
checks=[]
for r in z.itertuples():
 if r.accepted:
  qr,fs,par=s.getmeta(r.sid,pd.Timestamp(r.entry_day));q=int(r.quantity);px=s.D(str(r.entry_price));bf=s.fee(q,px,fs,'buy',par)
  assert qr.buy_floor(q)==q and q<=r.prior20_capacity and q*px+bf<=s.INIT and r.planned_risk<=float(s.NAV*s.D('.0025'))+1e-8
  if r.status=='COMPLETE':
   assert pd.Timestamp(r.exit_day)>pd.Timestamp(r.entry_day)
   _,xf,xp=s.getmeta(r.sid,pd.Timestamp(r.exit_day));sx=s.D(str(r.exit_price));sf=s.fee(q,sx,xf,'sell',xp);net=q*sx-sf-(q*px+bf)
   assert np.isclose(float(net),r.net_pnl,rtol=1e-10,atol=1e-7)
   assert pd.Timestamp(r.exit_day)==s.cal[s.cal.get_loc(pd.Timestamp(r.failure_close))+1]
 for day in paths[(paths.sid==r.sid)&(paths.window==r.window)&(paths.arm==r.arm)&paths.failed].day:
  assert not ((z.sid==r.sid)&(z.window==r.window)&(z.arm==r.arm)&(z.birth_day==day)).any()
assert ((paths.new_S>=paths.old_S-1e-10)|paths.new_S.isna()).all()
assert (paths.loc[paths.failed,'raw_close']<=paths.loc[paths.failed,'old_S']).all()
assert len(z[(z.sid=='600396.SH')&(z.window=='2024_924')&(z.arm=='LOCAL')])==1
# A synthetic loss of amount history cannot erase a valid CONTROL birth or its UNION eligibility.
r=z[(z.arm=='CONTROL')].iloc[0];m=manifest[r.sid];p=pd.read_parquet(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet'))).reindex(s.cal);k=s.cal.get_loc(pd.Timestamp(r.birth_day));p.iloc[k-20:k,p.columns.get_loc('amount')]=np.nan;ft=s.features(p,k);assert ft['control'] and not ft['local_known'] and (ft['price_known'] and (ft['control'] or ft['local_known']))
# Six fixed candidate signal checks already passed in primary run and their paths remain independent of outcome labels.
assert len(events)==6
stats=[]
for win,g in paired.groupby('window'):
 q=g[g.UNION_total_comparable];nonzero=q[q.UNION_total_net_diff.abs()>1e-8];stats.append(dict(window=win,fully_observed_paired_stocks=len(q),unknown_pair_stocks=len(g)-len(q),paired_total_diff=float(q.UNION_total_net_diff.sum()),positive_pairs=int(nonzero.UNION_total_net_diff.gt(0).sum()),negative_pairs=int(nonzero.UNION_total_net_diff.lt(0).sum()),equal_pairs=len(q)-len(nonzero)))
unknown=[]
for (win,arm),g in z.groupby(['window','arm']):
 a=g[g.accepted&g.status.str.startswith('UNKNOWN')];unknown.append(dict(window=win,arm=arm,accepted_unknown_stock_count=a.sid.nunique(),unknown_dates=a[['sid','birth_day','unknown_day']].to_dict('records'),stop_policy='Stop this stock-arm-window at first unresolved root; no fabricated post-action flat state or later births. Counts are censored coverage, not all full-window market opportunities.'))
s.save('AUDIT.json',dict(legal_buys_capacity_fee_budget_risk=True,complete_sell_fee_net_recomputed=True,T1=True,exits_immediate_next_common_open=True,oldS_checked_before_monotonic_lift=True,no_failure_close_rebirth=True,control_survives_unknown_local_amount=True,sid600396_oct28_duplicate_probe=False,fully_observed_pairs=stats,unknown_coverage=unknown,case_outputs_excluded_main_summary=True,source_hashes_still_unchanged=all(s.sha(p)==h for p,h in s.read(O/'SOURCE_HASHES.json').items())))
print('PAIRED',json.dumps(stats));print(pd.DataFrame(s.rounds).to_string(index=False));print('NO_BUY',z[~z.accepted].to_string(index=False))
