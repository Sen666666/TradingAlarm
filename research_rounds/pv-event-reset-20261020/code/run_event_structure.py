import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trend_event_structure import event_frame
from run_competing_state import assets,volume,run,CampaignClaims,cash_check,claims_check,audit_episodes,manifest,write

def enriched(c,v):
 f=event_frame(c,v);f['close']=c;f['volume']=v;f['price_target']=event_frame(c,v,joint=False).target;f['legacy_target']=event_frame(c,v,reset_on_exit=False).target;return f

def draw(f,path,title):
 fig,ax=plt.subplots(4,1,figsize=(11,8),sharex=True);ax[0].plot(f.index,f.close,color='black');ax[0].plot(f.index,np.exp(f.structure_floor),label='structure pivot');ax[0].set_yscale('log');ax[0].set_title(title);ax[0].legend()
 for event,marker in [(1,'^'),(-1,'v')]:
  dates=f.index[f.event.eq(event)];ax[0].scatter(dates,np.exp(f.loc[dates,'confirmed_pivot']),marker=marker,s=20,label='confirmed pivot (shown on confirmation date)')
 ax[1].bar(f.index,f.volume,color='gray');ax[2].plot(f.index,f.confirmation,label='opposite excursion confirmation');ax[2].axhline(1,color='black',ls=':');ax[2].legend()
 for col in ['target','price_target','legacy_target']:ax[3].step(f.index,f[col],where='post',label=col,alpha=.7)
 ax[3].legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(path,dpi=100);plt.close(fig)

def trajectories(root,out):
 assert not (out/'validation.json').exists();protocol=json.loads((out/'protocol.json').read_text())
 ix=pd.bdate_range('2020-01-01',periods=230);warm=.001*np.sin(np.arange(100)*2*np.pi/10);common=np.r_[warm,np.arange(40)*.002,np.linspace(.078,.048,10)]
 paths={'drift':np.r_[warm,np.arange(130)*.002],'range':np.r_[warm,.03*np.sin(np.arange(130)*2*np.pi/10)],'jump_flat':np.r_[warm,np.full(130,.08)],'one_bar_shock':np.r_[warm,.08,np.zeros(129)],'recover':np.r_[common,np.linspace(.051,.20,80)],'reverse':np.r_[common,np.linspace(.045,-.15,80)],'drift_flat':np.r_[warm,np.arange(40)*.002,np.full(90,.078)]};stored={};syn=[]
 for name,y in paths.items():
  c=pd.Series(np.exp(y),index=ix);v=pd.Series(100.,index=ix);v.iloc[100:105]=800.;a=event_frame(c,v)
  pd.testing.assert_frame_equal(event_frame(c.iloc[:150],v.iloc[:150]),a.iloc[:150]);z=event_frame(c*10,v*100)
  np.testing.assert_allclose(a[['confirmation','target','event']],z[['confirmation','target','event']],atol=1e-7,rtol=1e-7,equal_nan=True)
  np.testing.assert_allclose(a.structure_floor+np.log(10),z.structure_floor,atol=1e-7,rtol=1e-7,equal_nan=True)
  stored[name]=a;f=enriched(c,v);f.to_csv(out/f'synthetic-{name}.csv',index_label='date');draw(f,out/f'synthetic-{name}.png',name)
  syn.append(dict(case=name,entries=int(a.entered.iloc[100:].sum()),exits=int(a.exited.iloc[100:].sum()),held=int(a.target.iloc[100:].sum()),legacy_held=int(f.legacy_target.iloc[100:].sum())))
 pd.testing.assert_frame_equal(stored['recover'].iloc[:150],stored['reverse'].iloc[:150])
 # Exact flat prices cannot create events, regardless of volume changes.
 flat=event_frame(pd.Series(1.,index=ix),pd.Series(np.tile([1.,100.],115),index=ix));assert flat.event.eq(0).all() and flat.target.eq(0).all()
 source=Path(protocol['source']);checks=[]
 for path in sorted(source.glob('*-signals.csv')):
  s=path.name.removesuffix('-signals.csv');old=pd.read_csv(path,index_col='date',parse_dates=True);c=old.close;v=old.volume;f=enriched(c,v);cut=len(c)//2
  legacy=event_frame(c,v,reset_on_exit=False);np.testing.assert_allclose(legacy.to_numpy(),old[legacy.columns].to_numpy(),rtol=1e-9,atol=1e-9,equal_nan=True)
  pd.testing.assert_frame_equal(event_frame(c.iloc[:cut],v.iloc[:cut]),event_frame(c,v).iloc[:cut])
  seq=f.entered.cumsum()
  for _,chunk in f.loc[f.target.eq(1)].groupby(seq):assert chunk.structure_floor.diff().dropna().ge(-1e-12).all()
  f.to_csv(out/f'{s}-signals.csv',index_label='date');checks.append(dict(symbol=s,entries=int(f.entered.sum()),exits=int(f.exited.sum()),volume_different_days=int(f.target.ne(f.price_target).sum())))
  for case in protocol['cases']:
   if case['symbol']==s:draw(f.loc[case['start']:case['end']],out/f"{case['id']}-trajectory.png",case['id']+' '+s)
 write(out/'validation.json',dict(synthetic=syn,real=checks,synthetic_prefix=7,real_prefix=len(checks),scale=True,shared_prefix=True,flat_volume_no_events=True,floor_monotone=True));manifest(out,'trajectory');print(json.dumps(syn),flush=True)

def accounts(root,out):
 assert (out/'pre-account-review.md').exists();assert not (out/'accounts.json').exists();groups,_=assets();rows=[]
 for group,items in groups.items():
  for name,col in [('pv','target'),('price','price_target')]:
   signals={}
   for s,a in items.items():
    f=pd.read_csv(out/f'{s}-signals.csv',index_col='date',parse_dates=True);np.testing.assert_allclose(f.close,a['signal'].close,rtol=1e-12,atol=1e-12,equal_nan=True);signals[s]=f[col]
   for sc,cost,fx,delay in [('base',15,10,0)]+([('cost2',30,20,0),('delay1',15,10,1)] if name=='pv' else []):
    case=f'{group}-{name}-{sc}';recipients={s:groups['hk7'][s] for s in ['HK09618','HK03690']};claims=CampaignClaims(items,recipients) if group=='hk7' else None
    m,path,orders,decisions=run(items,'2022-01-01','2026-10-16','score_change',cost,fx,delay,signals=signals,cadence='daily',security_claims=claims)
    check=claims_check(items,path,orders,cost,fx,recipients) if claims else cash_check(items,path,orders,cost,fx);ep,daily,shape=audit_episodes(items,path,orders,fx)
    assert max(check.values())<1e-6 and shape['max_daily_error']<1e-6;assert all(o['signal_date']<o['date'] for o in orders)
    path.to_parquet(out/f'{case}-path.parquet')
    for suffix,content in [('orders',orders),('decisions',decisions),('episodes',ep)]:write(out/f'{case}-{suffix}.json',content)
    pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False);rows.append(dict(case=case,**m,ledger=check,episodes=shape));write(out/'accounts.json',rows);print(case,m['total_return'],flush=True)
 manifest(out,'account')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['trajectories','accounts'],required=True);a=p.parse_args();pr=json.loads((a.out/'protocol.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 assert sha(a.out/'protocol.json')==json.loads((a.out/'freeze.json').read_text())['sha256']
 for name,digest in pr['code'].items():assert sha(Path(__file__).with_name(name))==digest
 for name,digest in pr['inputs'].items():assert sha(Path(name))==digest
 globals()[a.phase](a.root,a.out)
