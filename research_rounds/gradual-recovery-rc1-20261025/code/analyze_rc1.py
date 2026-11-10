"""Post-freeze price-path diagnostics, never fed back to causal rules."""
from common_rc1 import *
import pandas as pd

def future(f,dt,anchor,h):
 valid=f.loc[f.valid_price_observation.astype(bool)]
 i=valid.index.get_loc(dt);j=i+h
 if j>=len(valid) or valid.segment_id.iloc[i:j+1].nunique()!=1:return {f'complete{h}':False,f'ret{h}':np.nan,f'anchor_broken{h}':np.nan}
 path=valid.close.iloc[i+1:j+1].astype(float);broken=bool((path<anchor*(1-32*np.finfo(float).eps)).any())
 return {f'complete{h}':True,f'ret{h}':float(valid.close.iloc[j]/valid.close.iloc[i]-1),f'anchor_broken{h}':broken}

def main():
 verify();assert read(HERE/'results/receipt.json')['passed'];out=HERE/'analysis';out.mkdir(exist_ok=False);events=[];entries=[];traces={};windows=[]
 cases=read(M1/'report/figure-manifest.json')
 for sid in NAMES:
  folder=HERE/'inputs'/sid;f=pd.read_parquet(folder/'bars.parquet');b=pd.read_parquet(folder/'E0.parquet');old=pd.read_parquet(folder/'G1.parquet');ix=pd.read_parquet(folder/'IX.parquet');m=pd.read_parquet(folder/'M1.parquet');rc=pd.read_parquet(HERE/'results'/f'{sid}-RC1.parquet');g=pd.read_parquet(HERE/'results'/f'{sid}-G1-RC1.parquet');ni=pd.read_parquet(HERE/'results'/f'{sid}-IX-RC1.parquet')
  newentries=ni.entered.eq(1)&~ix.target.eq(1);addedbuy=ni.buy_event.astype(bool)&~ix.buy_event.astype(bool)
  z=f.join(old[['grade','score','proposal','promotion_blocked','acute_down','fresh_up']].add_prefix('old_')).join(g[['grade','score','rc_promoted','rc_promoted_to_warm','rc_only_fresh']].add_prefix('new_')).join(rc.add_prefix('rc_')).join(ix[['target','entered','exited','floor','buy_event']].add_prefix('ix_')).join(ni[['target','entered','exited','floor','buy_event']].add_prefix('nix_')).join(m[['mu21','mu63','mu126','short_score','long_score']]);z['extra_qualified']=ni.target.eq(1)&~ix.target.eq(1);z['new_only_entry']=newentries;z['added_buy_event']=addedbuy;z.to_parquet(out/f'{sid}-trace.parquet');traces[sid]=z
  for dt,row in rc.loc[rc.receipt].iterrows():
   d=dict(symbol=sid,name=NAMES[sid],date=str(dt.date()),year=dt.year,context=row.context,tier=int(row.tier),anchor=row.anchor,anchor_date=row.anchor_date,close=float(f.loc[dt,'close']),pre_high=row.pre_high,below_pre_high=bool(row.below_pre_high),old_grade=float(old.loc[dt,'grade']),new_grade=float(g.loc[dt,'grade']),rc_warm_promotion=bool(g.loc[dt,'rc_promoted_to_warm']),rc_usable_fresh=bool(g.loc[dt,'rc_only_fresh']),added_buy_event=bool(addedbuy.loc[dt]),new_only_entry=bool(newentries.loc[dt]),**future(f,dt,float(row.anchor),21),**future(f,dt,float(row.anchor),63));events.append(d)
  for mode,st,mask in [('original_IX',ix,ix.entered.eq(1)),('IX_RC1_new_only',ni,newentries)]:
   for dt in f.index[mask]:
    anchor=float(rc.loc[dt,'anchor']);entries.append(dict(symbol=sid,name=NAMES[sid],mode=mode,date=str(dt.date()),context=rc.loc[dt,'context'],grade=float(g.loc[dt,'grade'] if mode!='original_IX' else old.loc[dt,'grade']),anchor=anchor,**future(f,dt,anchor,21),**future(f,dt,anchor,63)))
  for case in [c for c in cases if c['symbol']==sid]:
   a=z.loc[case['start']:case['end']];e0=b.loc[a.index]
   windows.append(dict(id=case['id'],symbol=sid,name=NAMES[sid],start=case['start'],end=case['end'],rows=len(a),original_ix_starts=int(a.ix_entered.sum()),rc1_ix_starts=int(a.nix_entered.sum()),new_only_starts=int(a.new_only_entry.sum()),extra_qualified_days=int(a.extra_qualified.sum()),extra_days_down_background=int((a.extra_qualified&a.rc_context.eq('down')).sum()),new_warm_receipts=int(a.new_rc_promoted_to_warm.sum()),new_only_starts_down_background=int((a.new_only_entry&a.rc_context.eq('down')).sum()),local_receipts=int(a.rc_receipt.sum()),original_cold_new_warm_days=int((a.old_grade.le(-2)&a.new_grade.ge(2)).sum())))
 ev=pd.DataFrame(events);en=pd.DataFrame(entries);ev.to_parquet(out/'local-receipts.parquet',index=False);ev.to_csv(out/'local-receipts.csv',index=False);en.to_csv(out/'entry-price-diagnostics.csv',index=False);pd.DataFrame(windows).to_csv(out/'window-summary.csv',index=False)
 summary=[]
 for scope,start in [('full','1900-01-01'),('display2023','2023-01-01')]:
  a=ev.loc[ev.date.ge(start)]
  groups=[('all',a),('added_buy_events',a.loc[a.added_buy_event]),('new_only_entries',a.loc[a.new_only_entry]),('down_background_local',a.loc[a.context.eq('down')])]
  for name,b in groups:
   for h in [21,63]:
    complete=b.loc[b[f'complete{h}']];v=complete[f'ret{h}']
    summary.append(dict(scope=scope,group=name,horizon=h,events=len(b),complete_labels=len(complete),below_pre_high=int(b.below_pre_high.sum()),down_context=int(b.context.eq('down').sum()),mean=v.mean(),median=v.median(),negative_fraction=v.lt(0).mean(),anchor_break_fraction=complete[f'anchor_broken{h}'].eq(True).mean()))
 pd.DataFrame(summary).to_csv(out/'receipt-price-summary.csv',index=False);write(out/'receipt-price-summary.json',summary)
 # Explicit failures, not a replacement truth set or parameter optimization.
 fail=ev.loc[ev.added_buy_event&ev.complete21&(ev.ret21.lt(0)|ev.anchor_broken21.eq(True))].sort_values(['date','symbol']);fail.to_csv(out/'added-opportunity-failures.csv',index=False)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,new_accounts=0,local_receipts=len(ev),entry_labels=len(en),windows=len(windows),model_revisions_after_outputs=0,future_labels='fixed valid-price observations, incomplete/segment breaks unknown, no fees or execution',account_or_winning_trade_claims=False))
 print(pd.DataFrame(windows).query("id in ['fixed_au_user_decline','fixed_au_user_consolidation','fixed_semi_2022','fixed_semi_2025_26h1','fixed_semi_2026']").to_string(index=False),flush=True)
 print(pd.DataFrame(summary).query("scope=='display2023' and horizon==21").to_string(index=False),flush=True)
if __name__=='__main__':main()
