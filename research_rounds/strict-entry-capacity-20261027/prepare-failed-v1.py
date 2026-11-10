from study import *
import math
sys.path.append(str(ROOT/'research_rounds/pv-strength-b5-20261025/code'));ev=P.C.import_path('sec_b5_evidence',ROOT/'research_rounds/pv-strength-b5-20261025/code/evidence.py')
src=inspect.getsource(ev._event_facts).replace('def _event_facts(bars):','def entry_events(bars, multiplier=1.5):').replace('(math.sqrt(5) * sigma[ext])','(multiplier * math.sqrt(5) * sigma[ext])');env=dict(ev.__dict__);exec(src,env);fn=env['entry_events']
snap=Path(read(PRIOR/'input.json')['snapshot']['path'])
def calc(f,k):
 out=[]
 for seg,g in f.groupby('segment_id',sort=False):
  e,_=fn(g,k);active=False;floor=math.nan;rows=[]
  for t,r in g.iterrows():
   exited=False
   if active and ev.compare(float(r.close),floor)<=0:active=False;exited=True
   if e.loc[t,'event']==1:
    pivot=float(e.loc[t,'confirmed_pivot_price'])
    if active:floor=max(floor,pivot)
    elif not exited:active=True;floor=pivot
   rows.append({'date':t,'strict_target':active,'strict_floor':floor if active or exited else math.nan,'event':float(e.loc[t,'event'])})
  out.append(pd.DataFrame(rows).set_index('date'))
 return pd.concat(out) if out else pd.DataFrame({'strict_target':pd.Series(dtype=bool),'strict_floor':pd.Series(dtype=float),'event':pd.Series(dtype=float)},index=pd.DatetimeIndex([],name='date'))
def main():
 (O/'signals').mkdir();(O/'code/entry_kernel.py').write_text(src);cov=[];prefix=0
 ids=pd.read_csv(P.C.DESIGN/'proposed-pool.csv').symbol.tolist()
 for sid in ids:
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet');old=pd.read_parquet(snap/'facts'/f'{sid}.parquet');f=f.reindex(old.index);z=calc(f,1.5);base=calc(f,1.0)
  assert np.array_equal(base.strict_target.to_numpy(bool),old.e0_target.to_numpy(bool)),sid
  np.testing.assert_allclose(base.strict_floor,old.e0_floor,equal_nan=True,rtol=1e-12,atol=1e-10,err_msg=sid)
  z['original_buy']=old.i_buy.astype(bool);z['strict_buy']=z.original_buy & z.strict_target;z.to_parquet(O/'signals'/f'{sid}.parquet')
  for date in ['2024-12-31','2026-06-30']:
   q=calc(f.loc[:date],1.5);pd.testing.assert_frame_equal(q,z.loc[:date,q.columns],check_exact=True);prefix+=1
  t=z.loc['2024':];cov.append({'symbol':sid,'original_buy_days':int(t.original_buy.sum()),'strict_buy_days':int(t.strict_buy.sum()),'original_signal_hash':sha(snap/'facts'/f'{sid}.parquet'),'new_hash':sha(O/'signals'/f'{sid}.parquet')})
 pd.DataFrame(cov).to_csv(O/'signal-coverage.csv',index=False);save(O/'signal-validation.json',{'passed':True,'prefixes':prefix,'multiplier_one_exact_e0_series':len(cov),'strict_buy_is_subset':True});graphs()
def graphs():
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 cases=[('688498.SH','2025-09-01','2026-03-01'),('688048.SH','2025-09-01','2026-03-01'),('002987.SZ','2025-06-01','2025-12-01'),('300502.SZ','2026-03-01','2026-10-27'),('002439.SZ','2024-01-01','2024-07-01'),('688041.SH','2026-03-01','2026-10-27')];fig,axs=plt.subplots(4,3,figsize=(18,12),gridspec_kw={'height_ratios':[3,1,3,1]})
 for n,(sid,start,end) in enumerate(cases):
  i,j=2*(n//3),n%3;f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];z=pd.read_parquet(O/'signals'/f'{sid}.parquet').reindex(f.index);ax=axs[i,j];ax.plot(f.index,f.close,c='#333');ax.fill_between(f.index,f.low,f.high,alpha=.2,color='#aaa');a=z.original_buy.fillna(False).astype(bool);b=z.strict_buy.fillna(False).astype(bool);ax.scatter(f.index[a],f.close[a],s=20,color='#bbb',label='原I');ax.scatter(f.index[b],f.close[b],s=10,color='#2675aa',label='严格仍允许');ax.set_title(sid);ax.legend(fontsize=8);axs[i+1,j].bar(f.index,f.amount/1e8,color='#8096aa');axs[i+1,j].set_ylabel('成交额/亿元')
  for ax in [ax,axs[i+1,j]]:ax.tick_params(axis='x',rotation=20,labelsize=7)
 fig.tight_layout();fig.savefig(O/'entry-review.png',dpi=115)
if __name__=='__main__':main()
