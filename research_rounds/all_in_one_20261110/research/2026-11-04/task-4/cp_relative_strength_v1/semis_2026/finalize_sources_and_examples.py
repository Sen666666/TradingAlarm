"""Source verification and separately labelled requested out-of-pool example.
Only fixed 5/20/60 log-return arithmetic on saved data; no strategy/account/model.
"""
from pathlib import Path
import csv, hashlib, json, math
import pandas as pd

O=Path(__file__).resolve().parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
A=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2')
BM=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
def read(p):return json.loads(Path(p).read_text())
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
sha=read(O/'SOURCE_SHA256.json')
def bind(p):
 p=Path(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
im={r['series']:r for r in read(U/'INDUSTRY_MANIFEST.json')}
meta=read(A/'metadata.json')
verified=[]
for r in sm.values():
 if meta[r['symbol']].get('sector_id')!='URFI881121':continue
 for p,expected in r['output_sha256'].items():
  if p in sha:
   assert sha[p]==expected,(p,sha[p],expected)
   verified.append({'path':p,'expected_and_actual_sha256':expected})
for p,expected in im['URFI881121']['output_sha256'].items():
 if p in sha:
  assert sha[p]==expected
  verified.append({'path':p,'expected_and_actual_sha256':expected})
dump(O/'ORIGINAL_MANIFEST_SHA_VERIFICATION.json',{'checked_original_outputs':len(verified),'all_equal':True,'files':verified})

sid='688146.SH';sector=meta[sid]['sector_id'];assert sector=='URFI881172'
stock=pd.read_parquet(bind(sm[sid]['refs']['CP1_input']))
facts=pd.read_parquet(bind(sm[sid]['refs']['facts']))
cp=pd.read_parquet(bind(sm[sid]['refs']['CP1']))
industry=pd.read_parquet(bind(im[sector]['refs']['CP1_input']))
market=pd.read_csv(bind(BM/'canonical/USHI1B0300.csv'),parse_dates=['date']).set_index('date')
rec={r['confirmed_day']:r for r in read(bind(sm[sid]['refs']['receipts'])) if '2026-01-01'<=r['confirmed_day']<='2026-06-30'}
assert set(rec)=={d.strftime('%Y-%m-%d') for d in cp.loc['2026-01-01':'2026-06-30'].index[cp.loc['2026-01-01':'2026-06-30','receipt'].eq(True)]}
def val(f,d,col='close'):
 if d not in f.index:return None
 v=f.at[d,col]
 return None if pd.isna(v) else float(v)
def ret(f,d,b,segment=False):
 x,y=val(f,d),val(f,b)
 if x is None or y is None or min(x,y)<=0:return None
 if segment and f.loc[b:d,'segment_id'].nunique()!=1:return None
 return math.log(x/y)
z=[]
for ds,r in rec.items():
 d=pd.Timestamp(ds);p=market.index.get_loc(d)
 row={'sid':sid,'name':meta[sid]['name'],'day':ds,'original_static_industry':meta[sid]['industry'],'original_static_sector_id':sector,
      'scope':'Requested separate electronic-chemicals example; NOT a member of semiconductor126 or bought18/25.',
      'CP_canonical_receipt_id':r['receipt_id'],'stock_close':val(stock,d),'raw_close':val(facts,d,'raw_close'),
      'industry_close':val(industry,d),'market_close':val(market,d),'original_i_target':int(val(facts,d,'i_target'))}
 for n in [5,20,60]:
  b=market.index[p-n]
  s,i,m=ret(stock,d,b,True),ret(industry,d,b,True),ret(market,d,b)
  row.update({f'base_day_{n}':b.strftime('%Y-%m-%d'),f'stock_base_close_{n}':val(stock,b),f'industry_base_close_{n}':val(industry,b),f'market_base_close_{n}':val(market,b),
              f'stock_logreturn_{n}':s,f'industry_logreturn_{n}':i,f'market_logreturn_{n}':m,
              f'RS_stock_{n}':s-i if s is not None and i is not None else None,f'RS_ind_{n}':i-m if i is not None and m is not None else None})
 z.append(row)
dump(O/'ZHONGCHUAN_SEPARATE_ORIGINAL_INDUSTRY_ALL_CP.json',z)
if z:
 with (O/'ZHONGCHUAN_SEPARATE_ORIGINAL_INDUSTRY_ALL_CP.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=z[0].keys());w.writeheader();w.writerows(z)

# Fixed examples named in task / original fills, plus all-negative-RS CP dates.
allcp=read(O/'ALL_CANONICAL_CP_H1_RS.json')
examples=[r for r in allcp if r['sid'] in ['300666.SZ','301611.SZ','603061.SH'] and (r['day'] in ['2026-01-06','2026-01-15','2026-01-16','2026-01-19','2026-01-20','2026-01-28'] or (r['RS_stock_20'] is not None and r['RS_stock_20']<0))]
dump(O/'NAMED_POSITIVE_AND_NEGATIVE_RS_EXAMPLES.json',examples)
all25=read(O/'ALL25_ORIGINAL_SIGNAL_RS.json')
original=read(O.parents[1]/'upside_state_v1/examples_semis/ALL25_SAVED_ROLE_HOLDING_CHAINS.json')
bylayer={r['layer']:r for r in original}
probes=[]
for x in all25:
 r=x['RS_at_original_signal'];old=bylayer[x['layer']]
 probes.append({'layer':x['layer'],'sid':x['sid'],'name':x['name'],'signal_day':r['day'],'role':x['role'],
                 'RS_stock5':r['RS_stock_5'],'RS_stock20':r['RS_stock_20'],'RS_stock60':r['RS_stock_60'],'RS_ind20':r['RS_ind_20'],
                 'saved_lifecycle_net_daily_proxy_ledger':old['closed_net'],'saved_open_cash_balance_NOT_profit':old['still_open_cash_balance_not_profit'],
                 'scope':'Closed lifecycle outcome copied from original saved bought-layer evidence solely for diagnosis; not H1 account return, ex-ante label or a filtered strategy result.'})
dump(O/'ALL25_RS_AND_SAVED_LIFECYCLE_NOT_STRATEGY.json',probes)
dump(O/'ZHONGCHUAN_SOURCE_CONVENTIONS.json',{'static_metadata':meta[sid],'stock_refs':sm[sid]['refs'],'industry_manifest':im[sector],
                                           'canonical_CP_H1_count':len(z),'positive_RS20':sum(r['RS_stock_20'] is not None and r['RS_stock_20']>0 for r in z),
                                           'negative_RS20':sum(r['RS_stock_20'] is not None and r['RS_stock_20']<0 for r in z)})
bind(__file__);dump(O/'SOURCE_SHA256_WITH_SUPPLEMENT.json',sha)
print(json.dumps({'manifest_original_outputs_verified':len(verified),'zhongchuan_CP':len(z),'zhongchuan_pos20':sum(r['RS_stock_20'] is not None and r['RS_stock_20']>0 for r in z),
 'zhongchuan_neg20':sum(r['RS_stock_20'] is not None and r['RS_stock_20']<0 for r in z),'first':z[:2]},ensure_ascii=False,indent=2))
