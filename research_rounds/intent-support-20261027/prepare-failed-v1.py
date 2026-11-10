from study import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
snap=Path(read(PRIOR/'input.json')['snapshot']['path'])
CASES=[('688498.SH','2025-09-01','2026-03-01'),('688048.SH','2025-09-01','2026-03-01'),('002987.SZ','2025-06-01','2025-12-01'),('300502.SZ','2026-03-01','2026-10-27'),('002439.SZ','2024-01-01','2024-07-01'),('688041.SH','2026-03-01','2026-10-27')]
def graphs(overlay=False):
 fig,axs=plt.subplots(4,3,figsize=(18,12),gridspec_kw={'height_ratios':[3,1,3,1]})
 for k,(sid,start,end) in enumerate(CASES):
  i,j=2*(k//3),k%3;f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];ax=axs[i,j];ax.plot(f.index,f.close,c='#333',lw=1);ax.fill_between(f.index,f.low,f.high,color='#aaa',alpha=.3);ax.set_title(sid);axs[i+1,j].bar(f.index,f.amount/1e8,color='#7892a1');axs[i+1,j].set_ylabel('成交额/亿元')
  if overlay:
   g=pd.read_parquet(snap/'facts'/f'{sid}.parquet').reindex(f.index);z=pd.read_parquet(O/'signals'/f'{sid}.parquet').reindex(f.index);ax.plot(g.index,g.i_floor,label='原I保护',c='#b88624');mask=z.event.eq(1);ax.scatter(z.index[mask],z.loc[mask,'pivot'],s=20,label='更细低点确认',color='#237aab');ax.legend(fontsize=8)
  for a in [ax,axs[i+1,j]]:a.tick_params(axis='x',rotation=20,labelsize=7)
 fig.tight_layout();fig.savefig(O/('overlay.png' if overlay else 'raw.png'),dpi=115);plt.close(fig)
def prep():
 sys.path.append(str(ROOT/'research_rounds/pv-strength-b5-20261025/code'));ev=P.C.import_path('intent_b5_evidence',ROOT/'research_rounds/pv-strength-b5-20261025/code/evidence.py')
 source=inspect.getsource(ev._event_facts).replace('def _event_facts(bars):','def fast_events(bars):').replace('(math.sqrt(5) * sigma[ext])','(0.5 * math.sqrt(5) * sigma[ext])');(O/'code/fast_kernel.py').write_text(source);env=dict(ev.__dict__);exec(source,env);fn=env['fast_events'];(O/'signals').mkdir();records=[]
 ids=pd.read_csv(P.C.DESIGN/'proposed-pool.csv').symbol.tolist()
 for sid in ids:
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet');parts=[]
  for seg,g in f.groupby('segment_id',sort=False):
   z,_=fn(g);z=z[['event','confirmed_pivot_price','confirmed_pivot_date']].rename(columns={'confirmed_pivot_price':'pivot','confirmed_pivot_date':'pivot_date'});parts.append(z)
  z=pd.concat(parts).sort_index();z['close']=f.close;z.to_parquet(O/'signals'/f'{sid}.parquet')
  for date in ['2024-12-31','2026-06-30']:
   pp=[]
   for _,g in f.loc[:date].groupby('segment_id',sort=False):
    t,_=fn(g);pp.append(t[['event','confirmed_pivot_price','confirmed_pivot_date']].rename(columns={'confirmed_pivot_price':'pivot','confirmed_pivot_date':'pivot_date'}))
   q=pd.concat(pp).sort_index();pd.testing.assert_frame_equal(q,z.loc[:date,q.columns],check_exact=True)
  records.append({'sid':sid,'signal':sha(snap/'signals'/f'{sid}.parquet'),'facts':sha(snap/'facts'/f'{sid}.parquet'),'new':sha(O/'signals'/f'{sid}.parquet')})
 save(O/'signal-validation.json',{'passed':True,'prefixes':len(records)*2,'records':records});graphs(True)
if __name__=='__main__':graphs() if sys.argv[1]=='raw' else prep()
