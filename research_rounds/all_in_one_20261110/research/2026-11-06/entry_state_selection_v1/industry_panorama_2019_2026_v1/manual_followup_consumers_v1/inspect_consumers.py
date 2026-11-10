import pathlib,json,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
NAMES='美容护理、食品加工制造、饮料制造、家居用品、互联网电商、其他社会服务、小家电、服装家纺、白色家电、纺织制造、影视院线、教育、黑色家电、包装印刷、医药商业、贸易、厨卫电器、造纸、汽车服务及其他、机场航运'.split('、')
a=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv');c=pd.read_csv(P/'COVERAGE_90.csv');sel=c[c.name.isin(NAMES)];assert len(sel)==20 and sel.manual_records.eq(0).all()
im=json.loads((U/'INDUSTRY_MANIFEST.json').read_text());sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();prices={};sources={};monthly=[];yearly=[];daily=[];lines=[]
for n in NAMES:
 sid=sel[sel.name.eq(n)].iloc[0].sector;m=next(m for m in im if m['series']==sid)
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;sources[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);assert d.index.is_unique and d.index.is_monotonic_increasing and set(d.symbol.dropna())=={sid}
 good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 q=d.close[good].loc[:'2026-10-22'].astype(float);prices[sid]=q;z=q.loc['2018-01-01':];base=q.loc['2019':].iloc[0];aa=a[a.sector.eq(sid)]
 lines.append('\n## '+n+' '+sid+'; P/F='+str(int(sel[sel.sector.eq(sid)].iloc[0].research_pool_members))+'/'+str(int(sel[sel.sector.eq(sid)].iloc[0].current_all_members)))
 lines.append('月末=2019首日100：')
 for year,g in z.groupby(z.index.year):
  parts=[]
  for month,v in g.groupby(g.index.month):
   row=dict(sector=sid,name=n,month=f'{year}-{month:02}',last_date=str(v.index[-1].date()),close=float(v.iloc[-1]),normalized=float(v.iloc[-1]/base*100),low_date=str(v.idxmin().date()),low=float(v.min()),high_date=str(v.idxmax().date()),high=float(v.max()))
   monthly.append(row);parts.append(f'{month}:{row["normalized"]:.1f}')
  row=dict(sector=sid,name=n,year=int(year),low_date=str(g.idxmin().date()),low=float(g.min()/base*100),high_date=str(g.idxmax().date()),high=float(g.max()/base*100),year_end=float(g.iloc[-1]/base*100));yearly.append(row)
  lines.append(str(year)+' '+','.join(parts)+f' | low {row["low_date"]}={row["low"]:.1f}, high {row["high_date"]}={row["high"]:.1f}')
 prev=None
 for _,r in aa.iterrows():
  pre='' if prev is None else f'; vs prior base {(q.loc[r.start]/q.loc[prev.start]-1)*100:.1f}%; vs prior peak {(q.loc[r.end]/q.loc[prev.end]-1)*100:.1f}%; previous peak to this base {(q.loc[r.start]/q.loc[prev.end]-1)*100:.1f}%'
  lines.append(f'{r.record_id} {r.start}~{r.end} ret {r.industry_return_pct:.2f}% mdd {r.mdd_pct:.2f}% n/K/P/F {int(r.positive_members)}/{int(r.known_members)}/{int(r.research_pool_members)}/{int(r.current_all_members)} full {int(r.full_path_members)} med {r.member_median_pct:.2f}% top3 {r.top3_positive_share_pct:.2f}%'+pre)
  prev=r
 for d,v in z.items():daily.append(dict(sector=sid,name=n,date=str(d.date()),close=float(v)))
pd.DataFrame(monthly).to_csv(O/'MONTHLY_PATH.csv',index=False);pd.DataFrame(yearly).to_csv(O/'YEARLY_EXTREMA.csv',index=False);pd.DataFrame(daily).to_csv(O/'DAILY_PRICES.csv',index=False)
(O/'PATH_REVIEW.txt').write_text('\n'.join(lines)+'\n');(O/'INDUSTRY_SOURCE_HASHES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
print('20 sectors',len(a[a.name.isin(NAMES)]),'auxiliary records; files written',O)
