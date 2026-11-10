import pathlib,json,hashlib,pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=pathlib.Path(__file__).parent; P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
names='小金属 非金属材料 金属新材料 塑料制品 油气开采及服务 橡胶制品 农化制品 化学原料 化学制品 化学纤维 石油加工贸易 种植业与林业 农产品加工 建筑材料 环境治理 环保设备 电力 燃气 港口航运 公路铁路运输'.split()
c=pd.read_csv(P/'COVERAGE_90.csv'); c=c.set_index('name').loc[names].reset_index(); assert (c.manual_records==0).all()
a=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv'); a=a[a.name.isin(names)]
src={}; daily=[]; monthly=[]; annual=[]; joins=[]
def signal(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p)
 assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h;src[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol'])
 good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 return d.close[good].loc[:'2026-10-22'].astype(float)
im={m['series']:m for m in json.loads((U/'INDUSTRY_MANIFEST.json').read_text())}; price={s:signal(im[s]) for s in c.sector}
for _,r in c.iterrows():
 p=price[r.sector].loc['2018':];q=a[a.sector==r.sector].sort_values('start')
 for d,v in p.items():daily.append(dict(sector=r.sector,name=r['name'],date=d,close=v))
 for group,out in [(p.groupby(p.index.to_period('M')),monthly),(p.groupby(p.index.year),annual)]:
  for period,v in group:
   out.append(dict(sector=r.sector,name=r['name'],period=str(period),first_date=str(v.index[0].date()),last_date=str(v.index[-1].date()),first=v.iloc[0],last=v.iloc[-1],low_date=str(v.idxmin().date()),low=v.min(),high_date=str(v.idxmax().date()),high=v.max(),mdd_pct=(v/v.cummax()-1).min()*100))
 for k in range(1,len(q)):
  x=q.iloc[k-1]; y=q.iloc[k]; z=p.loc[x.end:y.start]
  joins.append(dict(sector=r.sector,name=r['name'],previous=x.record_id,next=y.record_id,previous_peak=x.end,next_base=y.start,peak_to_next_base_pct=(p[y.start]/p[x.end]-1)*100,days=(pd.Timestamp(y.start)-pd.Timestamp(x.end)).days,next_peak_vs_previous_peak_pct=(p[y.end]/p[x.end]-1)*100,merged_start=x.start,merged_end=y.end,merged_return_pct=(p[y.end]/p[x.start]-1)*100,merged_mdd_pct=(p.loc[x.start:y.end]/p.loc[x.start:y.end].cummax()-1).min()*100))
plt.rcParams['font.family']=['Arial Unicode MS','sans-serif']
for page in range(4):
 fig,axes=plt.subplots(5,1,figsize=(17,20))
 for ax,(_,r) in zip(axes,c.iloc[page*5:page*5+5].iterrows()):
  p=price[r.sector].loc['2018':]; b=p.iloc[0];ax.plot(p.index,p/b*100,lw=1)
  for _,w in a[a.sector==r.sector].iterrows():
   ax.scatter(pd.Timestamp(w.start),p[w.start]/b*100,c='green',s=12);ax.scatter(pd.Timestamp(w.end),p[w.end]/b*100,c='red',s=12);ax.annotate(w.record_id+' '+w.end[:7],(pd.Timestamp(w.end),p[w.end]/b*100),fontsize=7,rotation=25)
  ax.set_title(r['name']+' '+r.sector);ax.grid(alpha=.3);ax.set_yscale('log')
 fig.tight_layout();fig.savefig(O/f'DAILY_REVIEW_{page+1}.png',dpi=130);plt.close(fig)
pd.DataFrame(daily).to_csv(O/'DAILY_PATHS_20.csv',index=False);pd.DataFrame(monthly).to_csv(O/'MONTHLY_PATHS_20.csv',index=False);pd.DataFrame(annual).to_csv(O/'ANNUAL_PATHS_20.csv',index=False);pd.DataFrame(joins).to_csv(O/'ADJACENT_SEGMENT_BRIDGES.csv',index=False)
a.to_csv(O/'AUXILIARY_130_REVIEW_INPUT.csv',index=False);(O/'SOURCE_HASHES.json').write_text(json.dumps(src,ensure_ascii=False,indent=2));print('industries',len(c),'aux',len(a));print(pd.DataFrame(joins).round(1).to_string(index=False))
