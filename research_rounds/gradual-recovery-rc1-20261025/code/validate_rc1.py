"""Independent cash-free credit/provenance/price-label checks."""
from common_rc1 import *
import pandas as pd
from PIL import Image
def main():
 frozen=verify();mapping=read(HERE/'repair-freeze-v1.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in mapping.items())
 checks=0;upgrades=0;oldqual=0;volume_effect=0
 for sid in NAMES:
  e=pd.read_parquet(HERE/'inputs'/sid/'evidence.parquet');old=pd.read_parquet(HERE/'inputs'/sid/'G1.parquet');rc=pd.read_parquet(HERE/'results-v1'/f'{sid}-RC1.parquet');new=pd.read_parquet(HERE/'results-v1'/f'{sid}-G1-RC1.parquet');ix=pd.read_parquet(HERE/'inputs'/sid/'IX.parquet');ni=pd.read_parquet(HERE/'results-v1'/f'{sid}-IX-RC1.parquet');ab=pd.read_parquet(HERE/'results-v1'/f'{sid}-RC1-price-weight-ablation.parquet')
  previous=None
  for dt,r in rc.iterrows():
   if not r.ready:assert not r.receipt;continue
   bar=e.loc[dt]
   assert abs(r.delta5-math.sqrt(5)*r.s0)<1e-14 and abs(r.delta21-math.sqrt(21)*r.s0)<1e-14
   if r.reset:
    assert r.anchor==bar.close and r.credit==0 and r.frontier==0 and not r.receipt
   else:
    assert previous is not None and r.anchor==previous.anchor
    delta=r.frontier-previous.frontier
    assert delta>=-1e-14 and abs(r.increment-delta)<1e-14
    weight=min(2.,max(.5,math.sqrt(float(bar.volume)/r.v0)))
    assert abs(r.credit-previous.credit-delta*weight)<1e-12
    if r.receipt:
     assert float(bar.strength_r)>0 and delta>0
     assert r.x>=r.delta5-1e-12 and r.credit>=r.delta5-1e-12
   assert r.frontier*.5-1e-12<=r.credit<=r.frontier*2+1e-12
   previous=r;checks+=1
  for dt,r in new.loc[new.transition.eq('upgrade')].iterrows():
   assert bool(old.loc[dt,'fresh_up']) or bool(rc.loc[dt,'receipt'])
   if not old.loc[dt,'fresh_up']:assert r.grade<=min(r.proposal,r.rc_cap)
   upgrades+=1
  assert not (new.rc_promoted_to_warm&rc.context.eq('down')).any();assert not (ix.target.eq(1)&~ni.target.eq(1)).any()
  oldqual+=int(ix.target.eq(1).sum());volume_effect+=int(rc.receipt.ne(ab.receipt).sum())
 assert volume_effect>0
 # Price-label arithmetic from full source, independent of analyze.future.
 labels=pd.read_parquet(HERE/'analysis/local-receipts.parquet');count=0;incomplete=0
 for sid,a in labels.groupby('symbol'):
  f=pd.read_parquet(HERE/'inputs'/sid/'bars.parquet');f=f.loc[f.valid_price_observation];dates=list(f.index);index={str(x.date()):i for i,x in enumerate(dates)}
  for row in a.itertuples():
   i=index[row.date]
   for h in [21,63]:
    j=i+h;complete=j<len(f) and len(set(f.segment_id.iloc[i:j+1]))==1
    assert complete==getattr(row,f'complete{h}')
    if not complete:assert pd.isna(getattr(row,f'ret{h}'));incomplete+=1;continue
    answer=float(f.close.iloc[j]/f.close.iloc[i]-1);broken=any(float(x)<row.anchor*(1-32*np.finfo(float).eps) for x in f.close.iloc[i+1:j+1])
    assert abs(answer-getattr(row,f'ret{h}'))<1e-14 and broken==getattr(row,f'anchor_broken{h}');count+=1
 figures=list((HERE/'report/figures').glob('*.png'));assert len(figures)==32
 for p in figures:
  with Image.open(p) as im:im.verify()
 identities={}
 for directory in [M1,SRC,G1,B5]:
  obj=read(directory/'complete.json');expected=obj.get('artifacts',obj.get('sha256'));assert expected is not None
  assert all(sha(ROOT/p)==h for p,h in expected.items()),directory.name;identities[directory.name]=len(expected)
 registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in registry.items())
 write(HERE/'validation.json',dict(recorded_at=now(),passed=True,frozen_files=frozen,real_valid_credit_rows=checks,grade_upgrades_traced=upgrades,old_IX_qualified_days_retained=oldqual,volume_changed_receipt_days=volume_effect,price_labels_independently_verified=count,incomplete_labels_retained=incomplete,readable_figures=len(figures),old_artifacts_unchanged=identities,named_algorithm_files_unchanged=len(registry),prepared_exact_prefixes=30,physical_evidence_prefixes=4,new_accounts=0))
 print(read(HERE/'validation.json'),flush=True)
if __name__=='__main__':main()
