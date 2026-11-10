"""Read-only inventory of the user's existing A-share research data."""
import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/repos/my-quant/data/processed')
def summary(sub):
 f=next((BASE/sub).glob('*.parquet'));p=pq.ParquetFile(f)
 out={'path':str(f),'bytes':f.stat().st_size,'rows':p.metadata.num_rows,'columns':p.schema.names}
 if p.metadata.num_rows<50000:
  d=p.read().to_pandas();out['missing_fraction']={c:float(v) for c,v in d.isna().mean().items()}
  for c in ['trade_date','snapshot_date','known_from','observed_at','effective_start_date','effective_end_date']:
   if c in d:
    vals=d[c].dropna();out[c]={'min':str(vals.min()),'max':str(vals.max()),'unique':int(vals.nunique())}
 return out
out={'read_only':True,'files':[summary(s) for s in ['securities','security_memberships','daily_bars_history','adjusted_daily_bars','factors/limit_prices','factors/suspend_status']],
 'conclusion':'Large raw/adjusted price history exists, but security listing/delisting dates absent; execution-state coverage and point-in-time membership need validation. No reliable survivor-free full-market backtest yet.'}
pqfile=pq.ParquetFile(BASE/'daily_bars_history/daily_bars.parquet');parts=[]
for batch in pqfile.iter_batches(batch_size=500000,columns=['symbol','trade_date']):
 d=batch.to_pandas();parts.append(d.groupby('symbol').trade_date.agg(['min','max','count']))
x=pd.concat(parts).groupby(level=0).agg({'min':'min','max':'max','count':'sum'})
securities=pq.read_table(BASE/'securities/securities.parquet',columns=['symbol']).to_pandas()
out['price_coverage']={'symbols':len(x),'first':str(x['min'].min()),'last':str(x['max'].max()),'symbols_ending_before2025':int((x['max']<pd.Timestamp('2025-01-01')).sum()),'bar_symbols_absent_from_master':sorted(set(x.index)-set(securities.symbol)), 'first_bar_is_not_proof_of_ipo_date':True}
folder=ROOT/'results/stock-data-audit';folder.mkdir(exist_ok=True,parents=True)
x.to_csv(folder/'symbol-coverage.csv');(folder/'audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out['price_coverage'],ensure_ascii=False));print([(f['path'].split('/')[-2],f['rows']) for f in out['files']])
