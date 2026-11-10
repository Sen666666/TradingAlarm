"""One-change transfer test to existing ETF cash/share campaign engine."""
import json,hashlib
from pathlib import Path
from campaign_engine import run_campaign
from hk_extension import load_extended
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/campaign-low-atr-v1'
def main():
 OUT.mkdir(exist_ok=True)
 protocol=dict(change='Entry priority strength versus ATR / split-adjusted raw price; all other rules fixed',cases='A-listed,HK-listed,mixed; two priorities each',entry='ma',exit='trend',pyramid=True,risk_fraction=.005,cost_bps=15,fx_bps=10,start='2022-01-01',limitation='ETF-only mechanism transfer, not a substitute for A/HK individual-stock objective; surviving selected funds; small universe; market-access assumptions unresolved')
 p=OUT/'protocol.json'
 if p.exists() and json.loads(p.read_text())!=protocol:raise ValueError('changed protocol')
 p.write_text(json.dumps(protocol,indent=2))
 assets,audit=load_extended();(OUT/'data-audit.json').write_text(json.dumps(audit,indent=2))
 rows=[]
 for market in ['A','HK','mixed']:
  chosen={n:a for n,a in assets.items() if market=='mixed' or (a['currency']=='CNY' if market=='A' else a['currency']=='HKD')}
  for ranking in ['strength','low_atr']:
   name=f'{market}-{ranking}'
   m,p,o,c,s=run_campaign(chosen,entry='ma',exit_mode='trend',pyramid=True,ranking=ranking)
   m.update(case=name,market=market,ranking=ranking);rows.append(m)
   p.to_csv(OUT/(name+'-path.csv'));(OUT/(name+'-orders.json')).write_text(json.dumps(o));(OUT/(name+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)))
   (OUT/'results.json').write_text(json.dumps(rows,indent=2))
   print(name,{k:round(m[k],5) for k in ['cagr','max_drawdown','best252_return']},flush=True)
 (OUT/'engine-sha256.txt').write_text(hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
if __name__=='__main__':main()
