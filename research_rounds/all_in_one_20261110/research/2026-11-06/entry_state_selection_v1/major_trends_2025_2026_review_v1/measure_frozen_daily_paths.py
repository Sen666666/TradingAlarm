import pathlib,json,pandas as pd,numpy as np,hashlib
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
H=json.load(open(R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'))
M=pd.read_csv('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv',dtype=str).drop_duplicates('symbol').set_index('symbol')
names={r['sid']:next(iter(M[M.industry_index_symbol==r['sid']].industry_name),r['sid']) for r in H if r['industry']}
periods=[('2025全年','2024-12-31','2025-12-31'),('2026年内截至1022','2025-12-31','2026-10-22'),('跨年2025至2026年内','2024-12-31','2026-10-22'),('2025上半年','2024-12-31','2025-06-30'),('2025下半年','2025-06-30','2025-12-31'),('2026上半年','2025-12-31','2026-06-30'),('2026下半年截至1022','2026-06-30','2026-10-22'),('原账覆盖跨年','2024-12-31','2026-05-15')]
reps=['688498.SH','300666.SZ','301611.SZ','688256.SH','688981.SH','002371.SZ','600547.SH','600489.SH','601899.SH','600988.SH','002155.SZ','002716.SZ']
sources={};prices={};qa=[]
for r in H:
 if not r['industry'] and r['sid'] not in reps:continue
 sid=r['sid'];p=next(p for p in r['source_identity'] if p.endswith('/signal.parquet'))
 q=pd.read_parquet(p).loc['2024-12-31':'2026-10-22'];v=q.price_eligible.fillna(False)&q.observed_bar.fillna(False)&~q.source_invalid.fillna(True)&~q.synthetic_event_bar.fillna(True)&np.isfinite(q.close)&q.close.gt(0)
 sources[p]=hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
 assert sources[p]==r['source_identity'][p]
 prices[sid]=q.close.where(v)
 qa.append({'sid':sid,'kind':'industry' if r['industry'] else 'stock','rows':len(q),'valid':int(v.sum()),'invalid':int((~v).sum()),'base_exists':pd.Timestamp('2024-12-31') in q.index,'end_exists':pd.Timestamp('2026-10-22') in q.index,'adjustment_factor_min':float(q.adjustment_factor.min()),'adjustment_factor_max':float(q.adjustment_factor.max()),'source_hash':sources[p]})
# Gold is separate from A-share universe. Do not infer native account could hold it.
G=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/gold-chart-fit-20261024')
for sid in ['sge-Au9999','sina-AU0']:
 p=G/'data'/(sid+'.csv');q=pd.read_csv(p,index_col='date');q.index=pd.to_datetime(q.index);prices[sid]=q.close.loc['2024-12-31':'2026-10-22'];sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();names[sid]={'sge-Au9999':'上海黄金交易所Au99.99现货','sina-AU0':'沪金连续AU0 换月规则未知'}[sid]
def metric(s,start,end):
 t=s.loc[start:end];missing=int(t.isna().sum());t=t.dropna()
 if len(t)<2:return {}
 v=t.values;ds=t.index.strftime('%Y-%m-%d').tolist()
 lo=hi=0;up=down=0.;ui=uj=di=dj=0
 for j in range(1,len(v)):
  u=v[j]/v[lo]-1;dd=1-v[j]/v[hi]
  if u>up:up=u;ui=lo;uj=j
  if dd>down:down=dd;di=hi;dj=j
  if v[j]<v[lo]:lo=j
  if v[j]>v[hi]:hi=j
 k=int(np.argmax(v));n=int(np.argmin(v))
 return {'base_date':ds[0],'end_date':ds[-1],'n':len(v),'invalid_rows':missing,'period_return_pct':100*(v[-1]/v[0]-1),'base_close':v[0],'end_close':v[-1],'max_rise_pct':100*up,'rise_low':ds[ui],'rise_high':ds[uj],'max_drawdown_pct':100*down,'drawdown_peak':ds[di],'drawdown_trough':ds[dj],'peak_from_base_pct':100*(v[k]/v[0]-1),'peak_day':ds[k],'lowest_day':ds[n]}
rows=[]
for sid,s in prices.items():
 kind='industry' if sid.startswith('URFI') else 'gold_price' if sid.startswith(('sge','sina')) else 'stock'
 name=names.get(sid,M.loc[sid,'name'] if sid in M.index else sid)
 for label,start,end in periods:rows.append({'period':label,'sid':sid,'name':name,'kind':kind,**metric(s,start,end)})
df=pd.DataFrame(rows);ps=pd.DataFrame(prices);inds=[sid for sid in prices if sid.startswith('URFI')]
assert len(inds)==90 and ps[inds].notna().all().all()
overview=[]
for label,start,end in periods:
 t=df[(df.kind=='industry')&(df.period==label)]
 basket=(ps.loc[start:end,inds]/ps.loc[start,inds]).mean(axis=1)
 overview.append({'period':label,'rising':int((t.period_return_pct>0).sum()),'falling':int((t.period_return_pct<0).sum()),'median_return_pct':float(t.period_return_pct.median()),'over50_return':int((t.period_return_pct>=50).sum()),'over50_peak':int((t.peak_from_base_pct>=50).sum()),'over100_peak':int((t.peak_from_base_pct>=100).sum()),**metric(basket,start,end)})
print('OVERVIEW');print(pd.DataFrame(overview).to_string(index=False))
print('FOCUS');print(df[df.sid.isin(['URFI881121','URFI881169','sge-Au9999','sina-AU0'])].to_string(index=False))
for label in ['2025全年','2026年内截至1022','跨年2025至2026年内']:
 print('TOP',label);print(df[(df.kind=='industry')&(df.period==label)].sort_values('period_return_pct',ascending=False)[['sid','name','period_return_pct','peak_from_base_pct','peak_day','max_rise_pct','rise_low','rise_high','max_drawdown_pct','drawdown_peak','drawdown_trough']].head(15).to_string(index=False))
print('STOCKS');print(df[(df.kind=='stock')&df.period.isin(['2025全年','2026年内截至1022','跨年2025至2026年内'])][['period','sid','name','period_return_pct','peak_from_base_pct','peak_day','max_drawdown_pct','invalid_rows']].to_string(index=False))
import sys
if len(sys.argv)>1:
 O=pathlib.Path(sys.argv[1]);O.mkdir(exist_ok=True)
 df.to_csv(O/'ALL_FIXED_PERIOD_PRICE_PATHS.csv',index=False);pd.DataFrame(overview).to_csv(O/'90_INDUSTRY_OVERVIEW.csv',index=False);pd.DataFrame(qa).to_csv(O/'SOURCE_VALIDITY.csv',index=False);ps.to_csv(O/'VALID_DAILY_CLOSES.csv')
 json.dump(sources,open(O/'SOURCE_SHA256.json','w'),ensure_ascii=False,indent=2)
 for p,h in sources.items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h
 json.dump({'all_industry_rows_valid':True,'sources_unchanged':True,'industry_n':90,'stock_n':len(reps),'gold_series':2,'asof':'2026-10-22','account_end':'2026-05-15','not_account_execution':'gold spot/continuous futures not in1709; stocks adjusted price descriptive only and external payout UNKNOWN; fixed roster NON-PIT'},open(O/'PRICE_QA.json','w'),ensure_ascii=False,indent=2)
