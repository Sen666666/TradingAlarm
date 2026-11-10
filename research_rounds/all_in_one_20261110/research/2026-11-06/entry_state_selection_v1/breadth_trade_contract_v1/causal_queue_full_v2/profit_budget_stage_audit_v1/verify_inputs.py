import pandas as pd,json,sys
from pathlib import Path
from decimal import Decimal as D
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
P=R/'breadth_trade_contract_v1/causal_queue_full_v2'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
sm={x['symbol']:x for x in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'];names=rules['security_metadata']
panel=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet')
cal=pd.DatetimeIndex(sorted(panel.day.unique()));z=pd.read_csv(P/'rounds_clockfixed/ALL_SHADOW_ROUNDS.csv')
def meta(sid,d):
 s=str(pd.Timestamp(d).date());i=market_identity_on(rules,sid,s,proxies);v=version_on(rules['fee_versions'][i['venue']],s,proxies)['schedule'];return QuantityRule(**version_on(rules['quantity_versions'][sid],s,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x)for x in v['components'])),D(str(names[sid]['par_value']))
def fees(q,p,sid,d,side):
 _,fs,par=meta(sid,d);return sum(fs.incremental(side,D(q)*D(str(p)),{},{},1,shares=int(q),par_value=par).values(),D(0))
def val(q,p,sid,d):return D(q)*p-fees(q,p,sid,d,'sell')
def qty(sid,d,p,S,budget,riskmax):
 qr,_,_=meta(sid,d);q=qr.buy_floor(int(budget/p))
 while q:
  c=D(q)*p+fees(q,p,sid,d,'buy');v=val(q,S*D('.9995'),sid,d)
  if c<=budget and c-v<=riskmax:return q,float(c),float(c-v)
  q=qr.buy_floor(q-1)
 return 0,0.,0.
import hashlib
manifest=json.loads((P/'rounds_clockfixed/SOURCE_HASHES.json').read_text());checks=[]
for sid in ['688126.SH','605358.SH','002408.SZ','002583.SZ']:
 m=sm[sid];rawpath=next(p for p in m['source_sha256']if p.endswith('/signal.parquet')); paths=[rawpath,m['refs']['facts'],m['refs']['CP1']]
 for path in paths:
  digest=hashlib.sha256(Path(path).read_bytes()).hexdigest();expected=manifest.get(path,m.get('output_sha256',{}).get(path,m.get('source_sha256',{}).get(path)));assert digest==expected,(path,digest,expected);checks.append(dict(path=path,sha256=digest))
for sid in ['688126.SH','605358.SH']:
 h=pd.read_parquet(next(p for p in sm[sid]['source_sha256']if p.endswith('/signal.parquet')));f=pd.read_parquet(sm[sid]['refs']['facts']);g=h.loc['2026-06-11':'2026-06-30'];assert g.adjustment_factor.nunique()==1
 for col in ['source_kind','source_path','segment_id']:assert g[col].nunique()==1
 assert g.observed_bar.all()and g.price_eligible.all()and g.volume_eligible.all()and not g.source_invalid.any()
 assert f.loc['2026-06-11':'2026-06-30','i_target'].all()
 for d in ['2026-06-11','2026-06-26']:
  v=h.loc[:d,'raw_volume'];v=v[v.gt(0)];print('CAPACITY',sid,d,int(v.iloc[-20:].mean()*.01))
print('HASHES',json.dumps(checks,ensure_ascii=False,indent=2))
