"""Assess complete requested crosssections without reading any forward return."""
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/fundamental-calendar-pilot';DATA=ROOT/'data/candidate-fundamentals'
def main():
 candidates=pd.read_parquet(OUT/'candidate-snapshots.parquet');cache={};rows=[]
 for c in candidates.itertuples(index=False):
  completed=0;available=[];failures=0;empty=0;missing=0
  for offset in [1,2,3,4]:
   q=c.date.to_period('Q')-offset;key=f'{c.symbol}-{q.year}Q{q.quarter}'
   if key not in cache:
    p=DATA/f'{key}.json';cache[key]=json.loads(p.read_text()) if p.exists() else None
   d=cache[key]
   if d is None:missing+=1;continue
   if d.get('error_code')!='0' or d.get('exception'):failures+=1;continue
   completed+=1;empty+=not bool(d.get('rows'))
   for r in d.get('rows',[]):
    assert r['code']==d['code'] and pd.Timestamp(r['statDate'])==q.end_time.normalize()
    assert pd.Timestamp(r['pubDate'])>=pd.Timestamp(r['statDate'])
    if pd.Timestamp(r['pubDate'])<c.date and r.get('YOYPNI') not in ['',None]:available.append(r)
  latest=max(available,key=lambda r:(r['statDate'],r['pubDate'])) if available else None
  rows.append(dict(symbol=c.symbol,date=c.date,requested_windows_complete=completed==4,has_published_value=bool(latest),missing_requests=missing,failed_requests=failures,empty_requests=empty,latest_vendor_statDate=latest['statDate'] if latest else None,latest_vendor_pubDate=latest['pubDate'] if latest else None,ytd_attributable_growth_vendor=latest['YOYPNI'] if latest else None,vintage_verified=False))
 frame=pd.DataFrame(rows);frame.to_parquet(OUT/'coverage.parquet',index=False)
 summary=frame.groupby('date').agg(candidates=('symbol','size'),complete_requests=('requested_windows_complete','sum'),published_values=('has_published_value','sum'),missing_requests=('missing_requests','sum'),failed_requests=('failed_requests','sum'))
 summary['all_requests_complete']=summary.complete_requests.eq(summary.candidates);summary['all_have_value']=summary.published_values.eq(summary.candidates);summary.to_csv(OUT/'coverage-by-date.csv');print(summary.to_string())
 (OUT/'audit.json').write_text(json.dumps(dict(dates=len(summary),dates_all_requested_windows_complete=int(summary.all_requests_complete.sum()),dates_all_have_published_vendor_values=int(summary.all_have_value.sum()),candidate_rows=len(frame),vintage_certified_dates=0,limitation='Completeness of four requestedquarter responses isnot completeness of everyfiling/version; values areunverified snapshots. No returns read.'),indent=2))
if __name__=='__main__':main()
