"""All frozen IX events, plus matched-input legacy assets and synthetic controls."""
from common_m1 import *
from model_m1 import describe
import pandas as pd
import sys,importlib.util

def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def groups(df):
 rows=[]
 for scope,start in [('full','2015-01-01'),('recent','2023-01-01')]:
  a=df.loc[df.date.ge(start)]
  for field in ['profile','grade']:
   for key,g in a.groupby(field,dropna=False,observed=True):
    for h in [21,63]:
     vals=g[f'ret{h}'].dropna();sy=g.dropna(subset=[f'ret{h}']).groupby(['symbol','year'])[f'ret{h}'].mean()
     rows.append(dict(scope=scope,field=field,group=str(key),horizon=h,events=len(g),labels=len(vals),mean=vals.mean(),median=vals.median(),p10=vals.quantile(.1),p90=vals.quantile(.9),positive=vals.gt(0).mean(),stock_year_mean=sy.mean(),stock_year_groups=len(sy)))
 return pd.DataFrame(rows)

def checks():
 out=HERE/'technical-v4';out.mkdir(exist_ok=False)
 paths={};n=400;t=np.arange(n);wave=.003*np.sin(t*1.7)+.002*np.cos(t*.71)
 paths['slow_up']=wave+.001
 paths['slow_noisy_up']=.0007+.003*(-1.)**t
 paths['slow_down']=wave-.001
 paths['flat']=wave*0
 paths['fast_launch']=np.r_[wave[:200],wave[200:]+.008]
 paths['up_then_crash']=np.r_[wave[:250]+.002,-.15,wave[251:]-.001]
 paths['down_then_rebound']=np.r_[wave[:250]-.003,wave[250:]+.004]
 stats=[]
 for name,r in paths.items():
  close=100*np.exp(np.cumsum(r));f=pd.DataFrame(dict(close=close,volume=1000.,segment_id='a',valid_strength_observation=True,acute_down=r<-.05),index=pd.bdate_range('2000-01-01',periods=n))
  m=describe(f);m.to_parquet(out/f'{name}.parquet')
  assert m.loc[m.acute_down.astype(bool),'profile'].eq('acute_down').all()
  assert m.long_score.iloc[:126].isna().all()
  for cut in [126,199,250,300]:pd.testing.assert_frame_equal(describe(f.iloc[:cut]),m.iloc[:cut])
  g=f.copy();g.close*=137.;g.volume*=19
  q=describe(g)
  np.testing.assert_allclose(m.select_dtypes(include='number'),q.select_dtypes(include='number'),rtol=1e-9,atol=1e-7,equal_nan=True)
  assert (m.profile==q.profile).all()
  for h in [5,21,63,126]:
   rv=np.log(f.close/f.close.shift()).dropna().to_numpy();mu=rv[0]
   for x in rv[1:]:mu=2/(h+1)*x+(1-2/(h+1))*mu
   assert abs(mu-m[f'mu{h}'].iloc[-1])<1e-14
  expected=1.4826*np.median(abs(np.log(f.close/f.close.shift()).iloc[236:299]))
  assert abs(float(m.s.iloc[299])-max(expected,1e-8))<1e-14
  stats.append(dict(path=name,last_profile=m.profile.iloc[-1],last_short=m.short_score.iloc[-1],last_long=m.long_score.iloc[-1],crash_profile=m.profile.iloc[250]))
 pd.DataFrame(stats).to_csv(out/'synthetic-summary.csv',index=False)
 noisy=pd.read_parquet(out/'slow_noisy_up.parquet')
 assert noisy.mu21.iloc[-1]>0 and noisy.mu126.iloc[-1]>0
 # No forced slow grade: the inherited odd median window alternates scale on
 # alternating return magnitudes. Preserve that diagnostic, don't tune drift.
 assert noisy.s.iloc[-1]!=noisy.s.iloc[-2]
 write(out/'synthetic-checks.json',dict(passed=True,paths=len(paths),prefixes=4*len(paths),unit_checks=len(paths),hand_ew_checks=4*len(paths),exclude_current_scale=len(paths),unknown_long_checks=len(paths),new_accounts=0))

def main():
 verify()
 if (HERE/'technical-v4/synthetic-checks.json').exists():assert read(HERE/'technical-v4/synthetic-checks.json')['passed']
 else:checks()
 out=HERE/'analysis';out.mkdir(exist_ok=False);(out/'series').mkdir()
 labels=pd.read_parquet(GAP/'cohort-v1/all-event-labels.parquet');keys=set(labels.symbol);eventrows=[];identity=[]
 oldassets=set(list(NAMES)[:7]);allseries=[]
 for n,sid in enumerate(sorted(keys)):
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet');m=describe(f)
  for col in ['z5','z21']:
   mask=m[col].notna()&f[col].notna();delta=float(abs(m.loc[mask,col].astype(float)-f.loc[mask,col]).max())
   np.testing.assert_allclose(m.loc[mask,col],f.loc[mask,col],rtol=1e-12,atol=1e-10,err_msg=sid+col);identity.append(dict(symbol=sid,column=col,rows=int(mask.sum()),max_abs_delta=delta))
  events=m.loc[f.IX.astype(bool)].copy();events['symbol']=sid;events['date']=events.index.strftime('%Y-%m-%d');eventrows.append(events.reset_index(drop=True))
  if sid in NAMES:
   g=f.join(m.drop(columns=['segment_id','z5','z21','acute_down']),rsuffix='_m1');g.to_parquet(out/'series'/f'{sid}.parquet');allseries.append(sid)
  if (n+1)%300==0:print(dict(stocks=n+1),flush=True)
 d=pd.concat(eventrows,ignore_index=True)
 e=labels.merge(d.drop(columns=['z5','z21','segment_id'],errors='ignore'),on=['symbol','date'],how='left',validate='one_to_one',suffixes=('','_m1'));assert len(e)==481305 and e.profile.notna().all();e.to_parquet(out/'all-event-multiscale.parquet',index=False)
 groups(e).to_csv(out/'label-summary.csv',index=False)
 pd.DataFrame(identity).to_csv(out/'old-pace-identity.csv',index=False)
 # Seven original assets require exactly their original input and original E0,
 # not the full-market signal adapter or a mixed gold source.
 sys.path.insert(0,str(ROOT/'research_rounds/pv-strength-b5-20261025/code'))
 api=load('_m1_b5',ROOT/'research_rounds/pv-strength-b5-20261025/code/api.py');g1=load('_m1_grade',ROOT/'research_rounds/b5-g1-20261025/code/grade.py')
 prefixes=0;diagnostics=[]
 for sid in oldassets:
  b5dir=ROOT/'research_rounds/pv-strength-b5-20261025'
  f=pd.read_parquet(b5dir/'inputs'/f'{sid}.parquet')
  e=pd.read_parquet(b5dir/'results-v2'/sid/'evidence.parquet');g,events=g1.classify(e)
  base=pd.read_parquet(b5dir/'results-v2'/sid/'state.parquet').add_prefix('e0_');z=f.join(g.drop(columns=['segment_id']),rsuffix='_g1').join(base,rsuffix='_base');m=describe(z)
  for col in ['z5','z21']:
   mask=m[col].notna()&g[col].notna();np.testing.assert_allclose(m.loc[mask,col],g.loc[mask,col],rtol=1e-12,atol=1e-10)
  z=z.join(m.drop(columns=['segment_id','z5','z21','acute_down']),rsuffix='_m1');z.to_parquet(out/'series'/f'{sid}.parquet');allseries.append(sid)
  for cut in [max(127,len(f)//3),len(f)//2,len(f)-50]:
   pd.testing.assert_frame_equal(describe(z.iloc[:cut]),m.iloc[:cut]);prefixes+=1
 for sid in ['688256.SH','300308.SZ','300502.SZ']:
  z=pd.read_parquet(out/'series'/f'{sid}.parquet');m=describe(z)
  for cut in [127,len(z)//2,len(z)-50]:pd.testing.assert_frame_equal(describe(z.iloc[:cut]),m.iloc[:cut]);prefixes+=1
 for sid in allseries:
  z=pd.read_parquet(out/'series'/f'{sid}.parquet').loc['2023-01-01':];a=z[z.full_ready]
  diagnostics.append(dict(symbol=sid,name=NAMES[sid],rows=len(a),profiles=a.profile.value_counts().to_dict(),long_up_short_weak=int(a.profile.eq('long_strong_short_weak').sum()),slow_up=int(a.profile.eq('slow_up').sum()),slow_G1_hot=int((a.profile.eq('slow_up')&a.grade.ge(3)).sum()),normalization_only_positive_changes=int(((a.long_score.diff()>0)&(a.mu126.diff()<=0)&(a.mu63.diff()<=0)).sum())))
 write(out/'series-diagnostics.json',diagnostics)
 write(out/'receipt.json',dict(passed=True,full_market_stocks=len(keys),all_IX_events=len(labels),real_prefixes=prefixes,old_z_comparisons=len(identity),new_accounts=0,no_new_grades=True,no_new_entry_events=True,inputs_same_as_old_per_series=True))
 print(pd.read_csv(out/'label-summary.csv').query("scope=='recent' and horizon==63 and field=='profile'").to_string(index=False),flush=True)
if __name__=='__main__':main()
