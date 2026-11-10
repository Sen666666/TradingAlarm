"""Coverage diagnostics, not an investable point-in-time universe certificate."""
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-data-audit'
master=pd.read_csv(OUT/'master-crosswalk.csv',dtype={'symbol':str})
coverage=pd.read_csv(OUT/'symbol-coverage.csv')
merged=master.merge(coverage,on='symbol',how='left')
for col in ['ipoDate','outDate','min','max']:
    merged[col]=pd.to_datetime(merged[col],errors='coerce')
records=[]
for year in range(2015,2027):
    date=pd.Timestamp(f'{year}-01-01')
    listed=(merged.ipoDate<=date)&(merged.outDate.isna()|(merged.outDate>date))
    covered=(merged['min']<=date)&(merged['max']>=date)
    records.append(dict(date=str(date.date()),provider_known_listed=int(listed.sum()),local_range_covers=int((listed&covered).sum()),missing_or_truncated=int((listed&~covered).sum()),eventually_retired_missing=int((listed&~covered&merged.outDate.notna()).sum())))
summary={'scope':'SH/SZ provider master only; start/end coverage is necessary, not sufficient. Does not certify calendar, events, tradability or historical symbol identities.', 'local_symbols_exactly_6000_rows':int((coverage['count']==6000).sum()),'local_symbols_total':len(coverage),'annual_coverage':records}
(OUT/'dated-universe-audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
