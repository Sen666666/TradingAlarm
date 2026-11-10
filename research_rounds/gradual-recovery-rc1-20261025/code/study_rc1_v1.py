"""Replay one fixed RC1 description and shadow IX consumer; no money."""
from common_rc1 import *
from checks_rc1 import modules
from evidence_rc1 import recover
from grade_rc1 import classify_with_recovery
import pandas as pd

def main():
 verify();api,grade,policy,m1=modules();out=HERE/'results-v1';out.mkdir(exist_ok=False);summary=[];prefixes=[]
 for sid in NAMES:
  folder=HERE/'inputs'/sid;e=pd.read_parquet(folder/'evidence.parquet');b=pd.read_parquet(folder/'E0.parquet');g=pd.read_parquet(folder/'G1.parquet');m=pd.read_parquet(folder/'M1.parquet');f=pd.read_parquet(folder/'bars.parquet');oldix=pd.read_parquet(folder/'IX.parquet')
  rc,j=recover(e,m,g);price,_=recover(e,m,g,joint=False);new=classify_with_recovery(e,g,rc);disabled=classify_with_recovery(e,g,rc,enabled=False);newix=policy.project(e,b,new,'G1_IX')
  pd.testing.assert_frame_equal(disabled[g.columns],g,check_exact=True)
  assert (new.grade.dropna()>=g.grade.dropna()).all()
  assert not (oldix.target.eq(1)&~newix.target.eq(1)).any(),sid+'original IX qualification lost'
  upgrades=new.transition.eq('upgrade');assert new.loc[upgrades,'fresh_up'].all()
  assert new.loc[g.acute_down,'grade'].le(-3).all()
  assert not (rc.context.eq('down')&new.rc_only_fresh).any()
  assert rc.loc[rc.receipt,'increment'].gt(0).all()
  for name,z in [('RC1',rc),('RC1-price-weight-ablation',price),('G1-RC1',new),('IX-RC1',newix)]:z.to_parquet(out/f'{sid}-{name}.parquet')
  write(out/f'{sid}-journal.json',j)
  for n in [max(127,len(e)//3),len(e)//2,len(e)-50]:
   cr,jj=recover(e.iloc[:n],m.iloc[:n],g.iloc[:n]);cn=classify_with_recovery(e.iloc[:n],g.iloc[:n],cr);ci=policy.project(e.iloc[:n],b.iloc[:n],cn,'G1_IX')
   for k,(a,z) in enumerate([(cr,rc.iloc[:n]),(cn,new.iloc[:n]),(ci,newix.iloc[:n])]):pd.testing.assert_frame_equal(a,z,check_exact=True,check_dtype=k<2)
   assert jj==[x for x in j if x['date']<=str(e.index[n-1].date())];prefixes.append(dict(symbol=sid,length=n,passed=True))
  summary.append(dict(symbol=sid,name=NAMES[sid],rows=len(f),local_receipts=int(rc.receipt.sum()),below_pre_high_receipts=int((rc.receipt&rc.below_pre_high).sum()),down_background_receipts=int((rc.receipt&rc.context.eq('down')).sum()),rc_warm_promotions=int(new.rc_promoted_to_warm.sum()),old_ix_entries=int(oldix.entered.sum()),rc1_ix_entries=int(newix.entered.sum()),new_only_entries=int((newix.entered.eq(1)&~oldix.target.eq(1)).sum()),extra_qualified_days=int((newix.target.eq(1)&~oldix.target.eq(1)).sum()),old_qualified_days_lost=int((oldix.target.eq(1)&~newix.target.eq(1)).sum()),volume_changed_receipt_days=int(rc.receipt.ne(price.receipt).sum())))
  print(summary[-1],flush=True)
 # Physical prefixes rebuild the original market evidence and long channels,
 # not merely truncate precomputed indicators. Four exact ten-source prefixes.
 for sid in ['AU0','512480','300308.SZ','001309.SZ']:
  f=pd.read_parquet(HERE/'inputs'/sid/'bars.parquet');n=len(f)//2;sub=f.iloc[:n];a=api.run_b5(sub);g,_=grade.classify(a['evidence']);m=m1.describe(sub.assign(acute_down=g.acute_down));rc,j=recover(a['evidence'],m,g);new=classify_with_recovery(a['evidence'],g,rc);ix=policy.project(a['evidence'],a['state'],new,'G1_IX')
  for name,z in [('RC1',rc),('G1-RC1',new),('IX-RC1',ix)]:pd.testing.assert_frame_equal(z,pd.read_parquet(out/f'{sid}-{name}.parquet').iloc[:n],check_exact=True,check_dtype=name!='IX-RC1')
  prefixes.append(dict(symbol=sid,length=n,physical_market_rebuild=True,passed=True))
 pd.DataFrame(summary).to_csv(out/'summary.csv',index=False);write(out/'summary.json',summary);write(out/'prefixes.json',prefixes)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,assets=len(NAMES),prepared_prefixes=30,physical_prefixes=4,disabled_grade_identity_assets=10,original_IX_coverage_preserved_assets=10,new_accounts=0))
if __name__=='__main__':main()
