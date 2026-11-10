"""Clarify saved-event history vs live context, and publish fixed views only."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;B=O.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

def main():
 cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json');nodes={(n['domain'],n['sector']):n for n in cat};summaries={};points=[];events=[];sources={}
 fixed={'2022':['2022-06-17','2022-06-28','2022-09-16','2022-12-29'],
  '2023':['2023-01-19','2023-02-13','2023-03-14','2023-06-30','2023-08-25'],
  'OLD924':['2024-09-24','2024-09-27','2024-09-30','2024-10-08','2024-12-31'],
  'LOCAL2026':['2026-04-30','2026-05-07','2026-06-30']}
 for case,days in fixed.items():
  path=O/(case+'-FULL_TABLE.parquet');sources[str(path)]=sha(path);df=pd.read_parquet(path);additional=[]
  for (domain,sec),group in df.groupby(['domain','sector'],sort=False):
   node=nodes[domain,sec];p=Path(node['daily_result_path']);sources[str(p)]=sha(p);f=pd.read_parquet(p).loc[:group.day.max()]
   last=None;count=0;hist={}
   for day,r in f.iterrows():
    if 'price_advance' in r.events:last=day;count+=1
    hist[day]=(last,count)
   for i,row in group.iterrows():
    last,n=hist[row.day];additional.append(dict(index=i,last_historical_native_advance=last,historical_native_advance_count=n,
      last_current_context_native_advance=row.last_native_advance))
   summaries.setdefault(case,[]).append(dict(sector=sec,industry=group.industry.iloc[0],observations=len(group),
    H1_known=int(group.industry_H1_score.notna().sum()),F1_permitted=int(group.F1_permit.sum()),
    F1_mature_and_permitted=int((group.F1_permit&group.F1_mature).sum()),
    median_H1_rank=float(group.H1_rank_all_original_sectors.median()),
    I_buy_flag_Q_observations=int(group.I_entry_Q.sum()),canonical_CP1_Q_observations=None if case=='OLD924' else int(group.canonical_CP1_Q.sum()),
    stock_observations_are_not_independent_episodes=True))
  ad=pd.DataFrame(additional).set_index('index').reindex(df.index);new=df.join(ad)
  pd.testing.assert_frame_equal(new[df.columns],df,check_exact=True)
  new.to_parquet(O/(case+'-FULL_TABLE_WITH_HISTORY.parquet'),index=False)
  cols=['case','domain','day','sector','industry','F1_mode','F1_permit','F1_mature','context_started','context_first_advance',
        'last_current_context_native_advance','context_advance_count','last_historical_native_advance','historical_native_advance_count',
        'industry_H1_score','H1_rank_all_original_sectors','H1_rank_among_mature_permitted','breadth','ready_m',
        'I_entry_Q','canonical_CP1_Q','numeric_CP1_Q','price_return_21','price_return_63','date_at_21','date_at_63']
  points+=json.loads(new[new.day.isin(days)][cols].to_json(orient='records'))
  for r in new.itertuples(index=False):
   if len(r.events):events.append(dict(case=case,domain=r.domain,day=r.day,sector=r.sector,industry=r.industry,events=list(r.events),
    permit=r.F1_permit,mature=r.F1_mature,H1=r.industry_H1_score,rank=r.H1_rank_all_original_sectors,
    current_context_advances=r.context_advance_count,last_historical_advance=r.last_historical_native_advance))
 save('FIXED_POINT_ALL_SECTORS.json',points);save('ALL_SECTOR_WINDOW_SUMMARY.json',summaries);save('INDUSTRY_F1_EVENTS.json',events);save('ANNOTATION_SOURCE_SHA256.json',sources)
 print('HISTORY_FIELDS_ADDED',len(points),'fixed-point rows;',len(events),'saved industry event rows')

if __name__=='__main__':main()
