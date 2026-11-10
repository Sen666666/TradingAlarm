"""Read fixed original bars/receipts; arithmetic references only, no fill model."""
from pathlib import Path
from decimal import Decimal as D
import gzip,hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1]
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
mp=P/'manifest.json';records={r['series_id']:r for r in json.loads(mp.read_text())['series']}
sources={};sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources[str(mp)]=sha(mp)
bars={}
for sid,day in [('601601.SH','2024-09-10'),('002583.SZ','2024-11-04')]:
    rec=records[sid]['raw'];p=Path(rec['path']);assert sha(p)==rec['sha256']
    sources[str(p)]=sha(p);frame=pd.read_parquet(p)
    row=frame.loc[pd.to_datetime(frame.trade_date).eq(pd.Timestamp(day))].iloc[0]
    bars[sid]={'day':day,**{k:str(row[k]) for k in ['open','high','low','close','volume']},
               'price_eligible':bool(row.price_eligible),'observed_bar':bool(row.observed_bar),'source_invalid':bool(row.source_invalid)}
bp=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz';sources[str(bp)]=sha(bp)
with gzip.open(bp,'rt') as f:book=json.load(f)
t=next(t for t in book['trades'] if t['side']=='sell' and t['security_id']=='002583.SZ' and t['at'].startswith('2024-11-05') and any(p['layer']==2017 for p in t['parts']))
tb_ref=D(bars['601601.SH']['open'])*D('.9995');hai_ref=D(bars['002583.SZ']['open'])*D('.9995')
assert tb_ref==D('30.02498') and hai_ref==D('22.82858')
assert D(t['price'])==D('22.98850') and hai_ref<D(t['price'])
assert D(bars['002583.SZ']['high'])>D(bars['002583.SZ']['low'])
cp_path=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/stock-receipts/601601.SH.json')
sources[str(cp_path)]=sha(cp_path);cp=json.loads(cp_path.read_text())
between=[r for r in cp if '2024-09-09'<r['confirmed_day']<='2024-09-18']
assert [r['confirmed_day'] for r in between]==['2024-09-18']
out={'status':'PASS_FIXED_REFERENCE_ARITHMETIC_AND_NEXT_NEW_CP_DATE',
     'taibao_Sept10_raw_bar':bars['601601.SH'],'Sept10_OPEN_minus5bp_reference_only':str(tb_ref),
     'hai_Nov04_raw_bar':bars['002583.SZ'],'Nov04_OPEN_minus5bp_reference_only':str(hai_ref),
     'hai_original_Nov05_trade':t,'earlier_reference_is_lower_not_price_improvement':True,
     'taibao_new_CP_after_Sept09_through_Sept18':between,
     'next_CP_qualification_conditional':'Sep18 CLOSE is next new canonical CP; actual reapplication also needs prior proposed partial exit completed, no pending barrier and candidate-account authorization. No hypothetical exit completion is asserted.',
     'source_sha256':sources,'new_accounts':0,'new_backtests':0,'new_window_calls':0,'candidate_fills_created':0,'candidate_cash_or_PnL_created':0}
sources[str(Path(__file__))]=sha(__file__)
(O/'REFERENCE_PRICE_AND_DATE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':out['status'],'taibao_ref':str(tb_ref),'hai_ref':str(hai_ref),'original_hai_price':t['price'],'next_CP_dates':[r['confirmed_day'] for r in between]},ensure_ascii=False))
