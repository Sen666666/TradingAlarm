import pathlib, json, hashlib, os
import pandas as pd, numpy as np
P=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/industry_panorama_2019_2026_v1')
O=P/'prior29_tech_review_v1'; os.environ['MPLCONFIGDIR']=str(O/'mplconfig')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
TITLEFONT=FontProperties(fname='/System/Library/Fonts/STHeiti Light.ttc')
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
NAMES=['半导体','消费电子','通信设备','电子化学品','元件','软件开发','文化传媒','游戏','汽车整车']
END=pd.Timestamp('2026-10-22'); names=pd.read_csv(P/'COVERAGE_90.csv').set_index('sector').name.to_dict()
old=pd.read_csv(P/'MANUAL_RECORDS.csv'); aux=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv'); hashes={}; prices={}; sids={v:k for k,v in names.items() if v in NAMES}
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
for m in json.loads((U/'INDUSTRY_MANIFEST.json').read_text()):
 if m['series'] not in sids.values():continue
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p); assert sha(p)==h; hashes[p]=h
 d=pd.read_parquet(p); good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 prices[m['series']]=d.close[good].loc[:END].astype(float)
monthly=[]; gaps=[]
for name,sid in sids.items():
 p=prices[sid].loc['2018':]; aa=aux[aux.sector==sid].sort_values('start'); oo=old[old.sector==sid]
 for mo,q in p.groupby(p.index.to_period('M')):monthly.append(dict(name=name,month=str(mo),low_day=str(q.idxmin().date()),low=q.min(),high_day=str(q.idxmax().date()),high=q.max(),last=q.iloc[-1]))
 for (_,a),(_,b) in zip(list(aa.iterrows())[:-1],list(aa.iterrows())[1:]):
  q=p.loc[a.end:b.start];gaps.append(dict(name=name,from_id=a.record_id,to_id=b.record_id,peak=a.end,low=b.start,retracement_pct=(p[b.start]/p[a.end]-1)*100,days=(pd.Timestamp(b.start)-pd.Timestamp(a.end)).days,prior_peak_recovered=str(p.loc[b.start:][p.loc[b.start:]>=p[a.end]].index.min().date()) if len(p.loc[b.start:][p.loc[b.start:]>=p[a.end]]) else None))
 for part,(a,b) in enumerate([('2018-01-01','2022-12-31'),('2022-01-01','2026-10-22')]):
  q=p.loc[a:b];fig,ax=plt.subplots(figsize=(16,5));ax.plot(q.index,q.values,lw=1,color='#233f69'); ax.set_title(name+' / '+sid+' / '+a[:4]+'-'+b[:4],fontproperties=TITLEFONT);ax.grid(alpha=.2)
  for _,r in aa.iterrows():
   if r.end<a or r.start>b:continue
   ax.scatter([pd.Timestamp(r.start),pd.Timestamp(r.end)],[p[r.start],p[r.end]],s=25,color=['green','red']);ax.annotate(r.record_id, (pd.Timestamp(r.end),p[r.end]),fontsize=7,rotation=45)
  for i,(_,r) in enumerate(oo.iterrows()):
   if r.end<a or r.start>b:continue
   ax.axvspan(pd.Timestamp(r.start),pd.Timestamp(r.end),alpha=.06,color='orange');ax.text(pd.Timestamp(r.start),ax.get_ylim()[0]+(i%3)*.08*(ax.get_ylim()[1]-ax.get_ylim()[0]),r.record_id,fontsize=8)
  ax.set_xlim(pd.Timestamp(a),pd.Timestamp(b));fig.tight_layout();fig.savefig(O/f'{sid}_{part}.png',dpi=110);plt.close(fig)
pd.DataFrame(monthly).to_csv(O/'MONTHLY_PATH_REVIEW.csv',index=False);pd.DataFrame(gaps).to_csv(O/'CANDIDATE_GAP_REVIEW.csv',index=False)
print(pd.DataFrame(gaps).to_string(index=False));print('SERIES',sids)
(O/'industry_source_hashes.json').write_text(json.dumps(hashes,indent=2))
