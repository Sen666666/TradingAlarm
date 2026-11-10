import os,pathlib,json,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent;R=P.parent
os.environ['MPLCONFIGDIR']=str(O/'mplcache')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
NAMES='建筑装饰 通用设备 专用设备 光学光电子 其他电子 汽车零部件 计算机设备 物流 保险 通信服务 综合 军工装备 自动化设备 工程机械 轨交设备 IT服务 军工电子 电机 电网设备 其他电源设备 多元金融'.split()
C=pd.read_csv(P/'COVERAGE_90.csv');C=C[C.name.isin(NAMES)];assert len(C)==21 and C.manual_records.eq(0).all()
A=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv');A=A[A.sector.isin(C.sector)].copy();S={};prices={}
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def loadj(p):S[str(p)]=sha(p);return json.loads(p.read_text())
def readprice(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;S[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);sid=m.get('series',m.get('symbol'));assert set(d.symbol.dropna())=={sid};assert d.index.is_unique and d.index.is_monotonic_increasing
 good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 return d.close[good].loc[:'2026-10-22']
for m in loadj(U/'INDUSTRY_MANIFEST.json'):
 if m['series'] in set(C.sector):prices[m['series']]=readprice(m)
monthly=[];trans=[]
for _,c in C.iterrows():
 p=prices[c.sector];q=p.loc['2018-01-01':];base=q.iloc[0]
 for d,v in q.resample('ME').last().items():monthly.append(dict(sector=c.sector,name=c['name'],month=str(d.date()),normalized_close=100*v/base))
 prev=None
 for _,a in A[A.sector==c.sector].iterrows():
  if prev is not None:
   st=pd.Timestamp(a.start);pe=pd.Timestamp(prev.end);ps=pd.Timestamp(prev.start);en=pd.Timestamp(a.end);bridge=p.loc[pe:st];newpeak=p.loc[pe:en];recover=newpeak[newpeak>p[pe]]
   trans.append(dict(sector=c.sector,name=c['name'],previous=prev.record_id,next=a.record_id,prior_start=prev.start,prior_peak=prev.end,next_trough=a.start,next_peak=a.end,bridge_drop_pct=(p[st]/p[pe]-1)*100,next_trough_vs_prior_start_pct=(p[st]/p[ps]-1)*100,next_peak_vs_prior_peak_pct=(p[en]/p[pe]-1)*100,recovery_date=str(recover.index[0].date()) if len(recover) else None))
  prev=a
pd.DataFrame(monthly).to_csv(O/'MONTHLY_PATHS.csv',index=False);pd.DataFrame(trans).to_csv(O/'ADJACENT_PATH_REVIEW.csv',index=False)
for i in range(3):
 fig,axes=plt.subplots(7,1,figsize=(15,22));
 for ax,(_,c) in zip(axes,C.iloc[7*i:7*i+7].iterrows()):
  p=prices[c.sector].loc['2018-01-01':];ax.plot(p.index,100*p/p.iloc[0]);ax.set_title(c.sector+' '+str(NAMES.index(c['name'])+1));ax.grid();ax.set_yscale('log')
  for _,a in A[A.sector==c.sector].iterrows():
   for col,color in [('start','g'),('end','r')]:
    d=pd.Timestamp(a[col]);
    if d>=p.index[0]:ax.scatter(d,100*prices[c.sector][d]/p.iloc[0],color=color,s=10)
 fig.tight_layout();fig.savefig(O/f'PATHS_{i+1}.png',dpi=120);plt.close(fig)
(O/'SOURCE_HASHES_PATHS.json').write_text(json.dumps(S,indent=2)+'\n')
print(C[['sector','name']].to_string(index=False));print('read',len(prices),'aux',len(A));print(pd.DataFrame(trans).round(2).to_string(index=False))
