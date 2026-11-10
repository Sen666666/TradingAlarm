import pathlib,json,hashlib,pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
names=['煤炭开采加工','钢铁','工业金属','贵金属','能源金属','光伏设备','风电设备','电池']
c=pd.read_csv(P/'COVERAGE_90.csv').set_index('name').loc[names].reset_index()
a=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv').query('name in @names');old=pd.read_csv(P/'MANUAL_RECORDS.csv').query('name in @names');src={}
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
for p in [P/'COVERAGE_90.csv',P/'AUXILIARY_20PCT_WAVES.csv',P/'MANUAL_RECORDS.csv',P/'MEMBER_RETURNS_ALL.csv',U/'INDUSTRY_MANIFEST.json',U/'STOCK_MANIFEST.json']:src[str(p)]=sha(p)
def signal(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;src[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 assert d.index.is_unique and d.index.is_monotonic_increasing
 return d.close[good].loc[:'2026-10-22'].astype(float)
im={m['series']:m for m in json.loads((U/'INDUSTRY_MANIFEST.json').read_text())};prices={s:signal(im[s]) for s in c.sector};daily=[];monthly=[];bridges=[]
for _,r in c.iterrows():
 p=prices[r.sector];q=a[a.sector==r.sector].sort_values('start')
 for d,v in p.loc['2018':].items():daily.append(dict(sector=r.sector,name=r['name'],date=str(d.date()),close=v))
 for period,v in p.loc['2018':].groupby(p.loc['2018':].index.to_period('M')):
  monthly.append(dict(sector=r.sector,name=r['name'],month=str(period),first_date=str(v.index[0].date()),last_date=str(v.index[-1].date()),first=v.iloc[0],last=v.iloc[-1],low_date=str(v.idxmin().date()),low=v.min(),high_date=str(v.idxmax().date()),high=v.max(),mdd_pct=(v/v.cummax()-1).min()*100))
 for k in range(1,len(q)):
  x,y=q.iloc[k-1],q.iloc[k];z=p.loc[x.start:y.end]
  bridges.append(dict(name=r['name'],previous=x.record_id,next=y.record_id,previous_peak=x.end,next_base=y.start,peak_to_next_base_pct=(p[y.start]/p[x.end]-1)*100,days=(pd.Timestamp(y.start)-pd.Timestamp(x.end)).days,next_peak_vs_previous_peak_pct=(p[y.end]/p[x.end]-1)*100,merged_start=x.start,merged_end=y.end,merged_return_pct=(p[y.end]/p[x.start]-1)*100,merged_mdd_pct=(z/z.cummax()-1).min()*100))
plt.rcParams['font.family']=['Arial Unicode MS','sans-serif']
for page in range(2):
 fig,axes=plt.subplots(4,1,figsize=(20,17))
 for ax,(_,r) in zip(axes,c.iloc[page*4:page*4+4].iterrows()):
  p=prices[r.sector].loc['2018':];b=p.iloc[0];ax.plot(p.index,p/b*100,lw=1)
  for _,w in a[a.sector==r.sector].iterrows():
   ax.scatter(pd.Timestamp(w.start),p[w.start]/b*100,c='green',s=15);ax.scatter(pd.Timestamp(w.end),p[w.end]/b*100,c='red',s=15);ax.annotate(w.record_id+' '+w.end[:7],(pd.Timestamp(w.end),p[w.end]/b*100),fontsize=8,rotation=25)
  for _,w in old[old.sector==r.sector].iterrows():ax.plot([pd.Timestamp(w.start),pd.Timestamp(w.end)],[p[w.start]/b*100,p[w.end]/b*100],lw=2,alpha=.35,c='purple')
  ax.set_title(r['name']+' '+r.sector);ax.grid(alpha=.3);ax.set_yscale('log')
 fig.tight_layout();fig.savefig(O/f'DAILY_REVIEW_{page+1}.png',dpi=115);plt.close(fig)
pd.DataFrame(daily).to_csv(O/'DAILY_PATHS_8.csv',index=False);pd.DataFrame(monthly).to_csv(O/'MONTHLY_PATHS_8.csv',index=False);pd.DataFrame(bridges).to_csv(O/'ADJACENT_SEGMENT_BRIDGES.csv',index=False)
a.to_csv(O/'AUXILIARY_67_INPUT.csv',index=False);old.to_csv(O/'OLD_MANUAL_28_INPUT.csv',index=False);(O/'SOURCE_HASHES.json').write_text(json.dumps(src,ensure_ascii=False,indent=2));print(pd.DataFrame(bridges).round(2).to_string(index=False))
