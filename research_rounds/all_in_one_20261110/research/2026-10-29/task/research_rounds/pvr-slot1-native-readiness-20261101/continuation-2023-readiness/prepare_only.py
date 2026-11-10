"""2023 original PVR/input and own-2022-state readiness; no account events."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,gzip,hashlib,pickle,time,collections
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;W=P.parent
sys.path.insert(0,str(P));import native_rank as N
J=N.J
FML=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
EXPECTED='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def gz(p,lines=False):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
 t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)

def main():
 begin=time.monotonic();assert sha(FML)==EXPECTED
 env=dict(np=np,pd=pd);exec(compile(FML.read_text(),str(FML),'exec'),env);score=env['score']
 oldmanifest=read(P/'SCORES_MANIFEST.json');old={r['symbol']:r for r in oldmanifest['entries']}
 baseline=W/'recovery-2023-readiness-20261101'
 alldays=gz(baseline/'runs/Bdiag/pair/daily.jsonl.gz',True)
 cal2023=[r['at'][:10] for r in alldays if '2023-01-03'<=r['at'][:10]<='2023-12-29']
 cal2022=oldmanifest['decision_calendars']['2022']['dates'];assert len(cal2022)==len(cal2023)==242
 dates=pd.DatetimeIndex(cal2022+cal2023,name='day')
 sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');assert len(sm)==1709
 manifests=[];coverage=[];prefix=[];start=time.monotonic()
 for i,r in enumerate(sm,1):
  sid=r['symbol'];src=Path(old[sid]['source']);assert sha(src)==old[sid]['source_sha256'];SRC[str(src)]=sha(src)
  oldpath=P/'scores'/f'{sid}.parquet';assert sha(oldpath)==old[sid]['output_sha256']
  op=O/'scores'/oldpath.name;meta=op.with_suffix('.json')
  if meta.exists():
   m=read(meta);assert sha(op)==m['output_sha256'] and m['source_sha256']==sha(src)
  else:
   f=pd.read_parquet(src).loc[:'2023-12-29'];z=score(f)
   old2022=pd.read_parquet(oldpath).loc[cal2022]
   pd.testing.assert_frame_equal(z[['score']].reindex(old2022.index),old2022,check_exact=True,check_freq=False)
   keep=z[['score']].reindex(dates);op.parent.mkdir(exist_ok=True)
   tmp=op.with_name(op.name+'.tmp');keep.to_parquet(tmp);tmp.replace(op)
   m=dict(symbol=sid,source=str(src),source_sha256=sha(src),formula_sha256=EXPECTED,
    input_cutoff='2023-12-29',full_warm_start=str(f.index.min()) if len(f) else None,
    output_rows=len(keep),ready_2023=int(keep.loc[cal2023].score.notna().sum()),NA_2023=int(keep.loc[cal2023].score.isna().sum()),
    old_2022_cells_exact=242,old_scores_file_sha256=sha(oldpath),output_sha256=sha(op))
   save(Path('scores')/meta.name,m)
   if sid in ['000001.SZ','300308.SZ','300502.SZ']:
    cut='2023-06-30';short=score(f.loc[:cut]);pd.testing.assert_frame_equal(short,z.loc[:cut],check_exact=True,check_freq=False)
    future=f.copy();future.loc[future.index>cut,'close']*=3;future.loc[future.index>cut,'amount']*=11
    pd.testing.assert_frame_equal(score(future).loc[:cut],z.loc[:cut],check_exact=True,check_freq=False)
    prefix.append(dict(sid=sid,cut=cut,physical_and_future_perturbed_prefix_exact=True))
  assert sha(oldpath)==old[sid]['output_sha256'],'old score cache was modified'
  fp=Path(r['refs']['facts']);assert sha(fp)==r['output_sha256'][str(fp)]
  ff=pd.read_parquet(fp,columns=['raw_close']);obs=ff.loc['2023-01-03':'2023-12-29']
  coverage.append(dict(sid=sid,source_observations_2023=len(obs),PVR_ready=m['ready_2023'],PVR_NA=m['NA_2023'],
                       missing_market_observations=242-len(obs)))
  manifests.append(m)
  if i%250==0:
   save('PROGRESS.json',dict(stocks=i,total=1709,seconds=time.monotonic()-start));print('2023_PVR_READY',i,'/',1709,round(time.monotonic()-start,2),flush=True)
 save('SCORES_MANIFEST.json',dict(stocks=1709,fixed_stock_ids=[r['symbol'] for r in sm],entries=manifests,
  formula_sha256=EXPECTED,windows=[['2022-01-01','2022-12-30'],['2023-01-03','2023-12-29']],
  decision_calendars=dict(past2022=cal2022,continuation2023=cal2023),
  explicit_cells=1709*484,source_cutoff='2023-12-29',original_2022_score_prefix_cells_exact=1709*242,
  old_score_manifest_sha256=sha(P/'SCORES_MANIFEST.json'),physical_prefix_checks=prefix,account_events=0))
 save('STOCK_COVERAGE.json',coverage)
 # Reuse original canonical trace exports, do not rerun I/E0/CP1/stage.
 rec=read(baseline/'inputs/MANIFEST.json');counts=collections.Counter();allkeys=set()
 for r in rec:
  p=Path(r['output_path']);assert sha(p)==r['output_sha256'];SRC[str(p)]=sha(p);rs=read(p)
  for x in rs:
   assert '2023-01-03'<=x['confirmed_day']<='2023-12-29'
   key=r['sid'],x['confirmed_day'],x['receipt_id'];assert key not in allkeys;allkeys.add(key)
  counts['industry' if r['industry'] else 'stock']+=len(rs)
 assert counts==dict(stock=18781,industry=1270),counts
 complete=read(baseline/'inputs/COMPLETION.json');assert complete['passed']
 # Read native own checkpoint. No Runner construction/restore/run is performed.
 checkpoint=P/'runs/2022/checkpoint.pkl';provenance=read(checkpoint.with_suffix('.provenance.json'))
 assert provenance['checkpoint_sha256']==sha(checkpoint);SRC[str(checkpoint)]=sha(checkpoint)
 payload=pickle.loads(checkpoint.read_bytes());b=gz(P/'runs/2022/pair/B.json.gz');a=payload['accounts']['B'];runner=payload['runner']
 assert str(payload['last_completed_event'])[:10]=='2022-12-30'
 for p,h in payload['source_freeze'].items():assert sha(p)==h
 mapping={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits',
          'audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
 checks={k:J.W.canon(a[k])==b[v] for k,v in mapping.items()};assert all(checks.values()),checks
 budget=a['budget'];assert type(budget) is N.BASE.NoAccountBudget
 assert runner['rank_mode']=='PVR_SLOT1' and runner['rank_scores_manifest_sha256']==sha(P/'SCORES_MANIFEST.json')
 engine=provenance['engine_identity'];assert engine['trading_class']['module_sha256']==sha(N.__file__)
 for name,fn in [('planning',N.Runner.planning),('opening',J.Runner.opening),('route',N.BASE.Runner.route)]:
  assert engine['functions'][name]['code_sha256']==N.IO._code_fingerprint(fn.__code__)
 # episode_starts is an immutable-data lookup, not capital state. It must extend.
 oldstarts=runner['episode_starts'];newstarts={}
 for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json'):
  q=pd.read_parquet(r['refs']['state']);q=q[q.day<='2023-12-29']
  for x in q.to_dict('records'):
   if x['E0_valid']:newstarts.setdefault(x['E0_episode'],pd.Timestamp(x['day']).date().toordinal())
 assert all(newstarts.get(k)==v for k,v in oldstarts.items())
 held={s for s,p in a['positions'].items() if p.shares};cov={x['sid']:x for x in coverage}
 state=dict(last_event=str(payload['last_completed_event']),NAV=str(a['current_nav']),available_cash=str(a['available']),
  global_observed_NAV_peak='1000000',C1_H_not_present=True,ACT_state=J.W.canon(a['risk_state']),
  held_stocks=len(held),live_layers=sum(x['qty']>0 for x in a['layers']),
  pending_buy_orders=len(a['buys']),pending_exit_orders=len(a['exits']),pending_next_open_intents=len(a['pending']),
  core_epoch_locks=len(a['core_epoch']),consumed_receipts=len(budget.consumed),loss_record_entries=len(budget.losses),
  cumulative_record_only_loss=budget.shared_loss,pool_probe=budget.resources('probe'),pool_confirmed=budget.resources('confirmed'),
  active_industries=sum(s.active for s in budget.sectors.values()),
  held_no_2023_observations=sorted(s for s in held if cov[s]['source_observations_2023']==0),
  held_with_some_missing_2023_dates=[cov[s] for s in sorted(held) if cov[s]['missing_market_observations']],
  old_checkpoint_sha256=sha(checkpoint),old_engine_identity=engine,book_field_checks=checks,
  old_episode_start_keys=len(oldstarts),extended_episode_start_keys=len(newstarts),
  old_episode_start_prefix_exact=True,
  import_blockers=['new score manifest hash is different: current generic restore must reject until explicit audited horizon import',
                  'generic restore overwrites episode_starts with2022 lookup: preserve verified2023 extended immutable lookup during explicit import'],
  no_state_restored_or_account_advanced=True)
 save('OWN_2022_TERMINAL_STATE.json',state)
 summary=dict(ready_for_continuation_wiring_review=True,full_financial_run_authorized=False,account_events=0,
  windows=['2022 own checkpoint','2023-01-03..2023-12-29'],fixed_stock_identities=1709,industries=90,market_dates_2023=242,
  stocks_no_2023_observations=sum(x['source_observations_2023']==0 for x in coverage),
  PVR_ready_cells_2023=sum(x['PVR_ready'] for x in coverage),PVR_NA_cells_2023=sum(x['PVR_NA'] for x in coverage),
  score_cells_2023=1709*242,original_2022_score_cells_exact=1709*242,
  canonical_receipts=dict(counts),scores_manifest_sha256=sha(O/'SCORES_MANIFEST.json'),
  old_scores_manifest_sha256=sha(P/'SCORES_MANIFEST.json'),
  old_2022_engine_and_book_exact=True,extended_episode_lookup_prefix_exact=True,
  existing_SC_2023_book=str(baseline/'runs/Bdiag/pair/B.json.gz'),
  technical_horizon_import_not_yet_implemented=True,first_Jan3_account_prefix_restart_not_executed=True,
  seconds=time.monotonic()-begin)
 save('READINESS.json',summary);save('SOURCE_SHA256.json',SRC)
 print('2023_READINESS',summary,flush=True);print('OWN_STATE',state['NAV'],state['available_cash'],state['ACT_state'],state['held_stocks'],flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),account_events=0));raise
