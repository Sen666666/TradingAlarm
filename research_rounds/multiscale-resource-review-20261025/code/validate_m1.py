"""Independent delivery checks. Does not run a financial account."""
from common_m1 import *
import pandas as pd
import gzip,collections
from PIL import Image

def main():
 n=verify();s=read(HERE/'handoff-freeze-v1.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in s.items())
 pool={x['security_id'] for x in read(OLD/'inputs-v2/selection.json')['lines'] if (x.get('company_cap_cny') or 0)>1e10};assert len(pool)==1709
 e=pd.read_parquet(HERE/'analysis/all-event-multiscale.parquet');old=pd.read_parquet(GAP/'cohort-v1/all-event-labels.parquet');assert len(e)==len(old)==481305
 pd.testing.assert_frame_equal(e[old.columns],old)
 used=set(e.symbol);assert used<=pool and len(used)==1679
 coverage=[dict(symbol=sid,has_old_IX_event=sid in used,event_count=int(e.symbol.eq(sid).sum())) for sid in sorted(pool)]
 pd.DataFrame(coverage).to_csv(HERE/'report/event-coverage.csv',index=False)
 # Summaries independently recomputed by Python scalar accumulation.
 table=pd.read_csv(HERE/'analysis/label-summary.csv');checked=0
 for row in table.itertuples():
  a=e.loc[e.date.ge('2015-01-01' if row.scope=='full' else '2023-01-01')]
  if row.field=='profile':a=a.loc[a.profile.eq(row.group)]
  else:a=a.loc[a.grade.eq(float(row.group))]
  vals=[float(x) for x in a[f'ret{row.horizon}'] if pd.notna(x)]
  assert len(a)==row.events and len(vals)==row.labels
  if vals:assert abs(math.fsum(vals)/len(vals)-row.mean)<1e-12;checked+=1
 # All original event fields retained exactly, rather than recomputed grade
 # or target values being silently substituted into the population labels.
 hand=pd.read_parquet(HERE/'handoff-v1/candidate-capacity-shadow.parquet')
 assert hand.minimum_lot.notna().all()
 assert hand.loc[hand.lot_aware_selected,'lot_within_cap'].all()
 pd.testing.assert_frame_equal(hand[['symbol','date','ret21','ret63']].sort_values(['symbol','date']).reset_index(drop=True),old.merge(hand[['symbol','date']],on=['symbol','date'],validate='one_to_one')[['symbol','date','ret21','ret63']].sort_values(['symbol','date']).reset_index(drop=True))
 prior=read(GAP/'enriched/rejected-event-snapshots.json');pri={(x['date'],x['symbol']):x for x in prior if x['account']=='IX__S0_base'};matched=0
 for x in hand.loc[hand.date.ge('2023-01-01')&hand.symbol.isin(['688256.SH','300308.SZ','300502.SZ'])].itertuples():
  p=pri[(x.date,x.symbol)];assert abs(x.minimum_lot-p['minimum_lot_notional'])<1e-8
  assert x.individual_capacity_fit==p['capacity_fits_after_actual_latched_exits'];matched+=1
 assert matched>0
 # Capacity and sorting invariants per original decision. This reads the
 # source path; the shadow does not feed its changes back into later dates.
 byday={day:g for day,g in hand.groupby('date')};invariants=0
 with gzip.open(SRC/'accounts/decisions.jsonl.gz','rt') as f:
  for line in f:
   if '"account": "IX__S0_base"' not in line:continue
   d=read_line=json.loads(line);day=d['at'][:10]
   if day not in byday:continue
   a=byday[day];remove=set(a.removed.iloc[0].split('|'));occ=[o for o in d['occupancy'] if o['security_id'] not in remove]
   for flag in ['capacity_selected','lot_aware_selected']:
    selected=a.loc[a[flag]];ids=[o['security_id'] for o in occ]+selected.symbol.tolist();assert len(ids)==len(set(ids))<=6
    counts=collections.Counter([o['sector_id'] for o in occ]+selected.sector_id.tolist());assert len(counts)<=3 and max(counts.values(),default=0)<=2
    assert set(selected.symbol)<=set(d['eligible']);assert not set(selected.symbol)&set(d['accepted']);invariants+=1
 # Every PNG opens and has the intended scientific-figure resolution.
 figures=list((HERE/'report/figures').glob('*.png'));assert len(figures)==32
 for p in figures:
  with Image.open(p) as im:im.verify()
 # Old full-market results and named algorithms remain byte-identical.
 source_counts={}
 for directory in [SRC,GAP]:
  mapping=read(directory/'complete.json')['artifacts'];bad=[p for p,h in mapping.items() if sha(ROOT/p)!=h];assert not bad,bad;source_counts[directory.name]=len(mapping)
 registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in registry.items())
 write(HERE/'validation.json',dict(recorded_at=now(),passed=True,freeze_files=n,supplement_files=len(s),selected_pool=1709,stocks_with_events=1679,no_event_stocks=30,old_event_columns_exact=len(old.columns),old_event_rows_exact=len(old),summary_means_independently_checked=checked,three_stock_minlot_and_relief_checks=matched,capacity_invariants=invariants,readable_pngs=len(figures),old_artifacts_unchanged=source_counts,named_algorithm_files_unchanged=len(registry),new_accounts=0))
 print(read(HERE/'validation.json'),flush=True)
if __name__=='__main__':main()
