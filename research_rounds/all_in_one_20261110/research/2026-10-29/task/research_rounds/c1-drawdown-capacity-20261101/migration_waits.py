"""Saved native-pool transitions after an observed C1 migration failure."""
from pathlib import Path
import gzip,json,statistics
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def main():
 for win in ['2022','2025_26']:
  p=O/'analysis'/win/'PROBE_MIGRATION_AND_RESOURCES.json'
  if not p.exists():continue
  failures=[r for r in read(p)['current_attempt_probe_cannot_fit_target_pool'] if r['explicit_failed_industry_migration_event']];first={}
  for r in failures:
   for lid in r['current_probe_layers']:first.setdefault(lid,r['day'])
  with gzip.open(O/'runs'/win/'pair/daily.jsonl.gz','rt') as f:ds=[json.loads(x) for x in f]
  dates=[r['at'][:10] for r in ds];ix={d:i for i,d in enumerate(dates)};snap={d:{l['id']:l for l in r['layers']} for d,r in zip(dates,ds)}
  with gzip.open(O/'runs'/win/'pair/B.json.gz','rt') as f:b=json.load(f)
  layers={x['id']:x for x in b['layers']};out=[]
  for lid,d in first.items():
   transferred=next((date for date in dates[ix[d]+1:] if lid in snap[date] and snap[date][lid]['pool']=='confirmed'),None);l=layers[lid]
   status='observed_migrated' if transferred else 'actually_exited_before_observed_migration' if l['closed'] else 'still_probe_censored_at_end'
   out.append(dict(layer=lid,sid=l['sid'],role=b['metadata'][str(lid)]['role'],first_explicit_failed_migration_close=d,first_later_confirmed_close=transferred,source_sessions_to_observed_migration=ix[transferred]-ix[d] if transferred else None,actual_exit=l['closed'],status=status,one_day_snapshot_resolution_not_exact_opening_timestamp=True))
  lags=[r['source_sessions_to_observed_migration'] for r in out if r['status']=='observed_migrated'];summary=dict(unit='one real probe lot after its first explicit industry-migration failure',layers=len(out),stocks=len({r['sid'] for r in out}),migrated=sum(r['status']=='observed_migrated' for r in out),exited=sum(r['status']=='actually_exited_before_observed_migration' for r in out),censored=sum(r['status']=='still_probe_censored_at_end' for r in out),migration_lag_median=statistics.median(lags) if lags else None,migration_lag_max=max(lags) if lags else None,exact_exclusive_probe_new_order_block_cause='not available from merged route-reason logs')
  target=O/'analysis'/win/'MIGRATION_WAIT_LOTS.json';target.write_text(json.dumps(dict(summary=summary,lots=out),ensure_ascii=False,indent=2)+'\n');print(win,summary)
if __name__=='__main__':main()
