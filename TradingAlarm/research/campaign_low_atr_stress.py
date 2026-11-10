"""Prespecified cost/delay checks for mixed ETF ranking transfer."""
import json
from campaign_engine import run_campaign
from hk_extension import load_extended
from campaign_low_atr import OUT
assets,_=load_extended();rows=[]
for name,kwargs in [('double_cost',dict(cost_bps=30,fx_bps=20)),('delay1',dict(extra_delay=1))]:
 m,p,o,_,_=run_campaign(assets,entry='ma',exit_mode='trend',pyramid=True,ranking='low_atr',**kwargs)
 m['case']=name;rows.append(m);p.to_csv(OUT/(name+'-path.csv'));(OUT/(name+'-orders.json')).write_text(json.dumps(o));(OUT/'stress.json').write_text(json.dumps(rows,indent=2));print(name,m,flush=True)
