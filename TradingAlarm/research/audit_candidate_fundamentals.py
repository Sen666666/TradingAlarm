"""Coverage and schema audit only; no vendor row is promoted to verified vintage."""
import json
from decimal import Decimal
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data/candidate-fundamentals';OUT=ROOT/'results/candidate-fundamentals'
def main():
 records=[];bad=[];empty=0;failed=0
 for p in sorted(DATA.glob('*.json')):
  d=json.loads(p.read_text())
  if d.get('error_code')!='0' or d.get('exception'):failed+=1;continue
  if not d.get('rows'):empty+=1;continue
  for row in d['rows']:
   try:
    assert row['code']==d['code'];stat=pd.Timestamp(row['statDate']);pub=pd.Timestamp(row['pubDate']);expected=pd.Period(f"{d['year']}Q{d['quarter']}").end_time.normalize();assert stat==expected and pub>=stat
    for field in ['YOYEquity','YOYAsset','YOYNI','YOYEPSBasic','YOYPNI']:
     if row[field]!='':assert Decimal(row[field]).is_finite()
    records.append(dict(symbol=d['symbol'],statDate=stat,pubDate=pub,YOYPNI=row['YOYPNI'],vintage_verified=False))
   except Exception as e:bad.append(dict(file=p.name,error=type(e).__name__))
 frame=pd.DataFrame(records);frame.to_parquet(OUT/'unverified-records.parquet',index=False)
 if len(frame):assert not frame.duplicated(['symbol','statDate','pubDate']).any()
 raw=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet',columns=['symbol','date','active20']);raw=raw[raw.active20.eq(20)].copy();groups={s:g for s,g in frame.groupby('symbol')};coverage=[]
 for row in raw.itertuples(index=False):
  q=pd.Timestamp(row.date).to_period('Q');g=groups.get(row.symbol);valid=pd.DataFrame() if g is None else g[(g.pubDate<row.date)&(g.statDate>= (q-4).start_time)&(g.statDate<q.start_time)&g.YOYPNI.ne('')]
  coverage.append(dict(symbol=row.symbol,date=row.date,has_published_vendor_value=not valid.empty,verified=False))
 c=pd.DataFrame(coverage);c.to_parquet(OUT/'candidate-coverage.parquet',index=False)
 report=dict(files=len(list(DATA.glob('*.json'))),records=len(frame),issuers=int(frame.symbol.nunique()) if len(frame) else 0,empty=empty,failed=failed,invalid=bad,candidate_rows=len(c),candidate_rows_with_published_vendor_value=int(c.has_published_vendor_value.sum()),verified_candidate_rows=0,limitations=['Partial deterministiccollection,notrepresentative coverage or performance','Publicationdatefilter avoids obviousdateleak only;versionsemantics unverified','Available partiallookback mayomit newerfilings;not certifiedlatestasof','Missingvalues notfilled withzero; knownrevisions mustremainseparatevintages'])
 verified_path=OUT/'verified-fields.json'
 verified=json.loads(verified_path.read_text()) if verified_path.exists() else []
 report['independently_verified_report_versions']=len(verified)
 report['independently_verified_field_versions']=sum(len(r['verified_original_fields']) for r in verified)
 report['verification_note']='Fieldspotchecks do not certify latest available filing completeness for candidate snapshots'
 (OUT/'coverage-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
