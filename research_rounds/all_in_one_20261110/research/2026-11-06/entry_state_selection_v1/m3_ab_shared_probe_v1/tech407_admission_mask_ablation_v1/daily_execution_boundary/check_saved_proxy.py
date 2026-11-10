"""Post-run daily OHLC diagnostic only; never feeds any admission or fill decision."""
from pathlib import Path
from decimal import Decimal as D,ROUND_HALF_UP
import hashlib,json,sys
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from runner import save,read
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
m=next(x for x in read(U) if x['symbol']=='300085.SZ');p=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')))
assert hashlib.sha256(p.read_bytes()).hexdigest()==m['source_sha256'][str(p)]
f=pd.read_parquet(p);rows=[]
for ds in ['2024-09-23','2024-09-24','2024-09-25','2024-09-26']:
    z=f.loc[pd.Timestamp(ds)];assert z.symbol=='300085.SZ'
    rows.append(dict(day=ds,**{k:z[k].item() if hasattr(z[k],'item') else z[k] for k in ['symbol','raw_open','raw_high','raw_low','raw_close','raw_volume','observed_bar','price_eligible','volume_eligible','source_kind','source_path','segment_id']}))
j=read(ROOT/'run_tech407_once/EXACT_TRADE_JOURNAL.json');rid='2024_924|A_UNION_B_SHARED_ENGINEERING_V1|300085.SZ|2'
initial=next(x for x in j if x['round_id']==rid and x['side']=='buy_core');add=next(x for x in j if x['round_id']==rid and x['side']=='buy_add')
limit_arithmetic=(D(str(f.loc[pd.Timestamp('2024-09-24'),'raw_close']))*D('1.20')).quantize(D('.01'),rounding=ROUND_HALF_UP)
v=dict(source_file=str(p),source_sha256=m['source_sha256'][str(p)],source_manifest_sha256=hashlib.sha256(U.read_bytes()).hexdigest(),daily_rows=rows,
    initial_exact_journal=initial,ADD_exact_journal=add,previous_close_times_1_20_rounded_cent=limit_arithmetic,
    september25_not_one_price_bar=f.loc[pd.Timestamp('2024-09-25'),'raw_low']<f.loc[pd.Timestamp('2024-09-25'),'raw_high'],
    ADD_proxy_price_above_observed_day_high=D(add['exact_price'])>D(str(f.loc[pd.Timestamp('2024-09-25'),'raw_high'])),
    initial_proxy_price_within_observed_day_range=D(str(f.loc[pd.Timestamp('2024-09-24'),'raw_low']))<=D(initial['exact_price'])<=D(str(f.loc[pd.Timestamp('2024-09-24'),'raw_high'])),
    interpretation='Sep25 daily bar is not one-price: low17.98 versus open/high/close18.98. Nonzero volume and lower later daily low do not certify opening auction/queue execution. Frozen conditional ADD proxy18.98949 is above observed high18.98 and cannot be presented as an executable exchange-price fill. Sep24 first probe proxy13.08654 lies within that daily range but also is not queue proof. The6381.771382861 actual model round NET80 remains a conditional-proxy result, not real capture assurance. No original account output or economic rule changed; no minute/tick/orderbook data used.')
save(HERE/'DAILY_BOUNDARY_300085.json',v)
save(HERE/'OUTPUT_SEAL.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file()})
print('DAILY_BOUNDARY_SAVED')
