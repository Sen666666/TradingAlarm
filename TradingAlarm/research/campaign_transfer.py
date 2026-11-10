import json
from campaign_engine import run_campaign
from hk_extension import load_extended
from portfolio_data import ROOT
OUT=ROOT/'results/campaign-v3'
OUT.mkdir(exist_ok=True,parents=True)
assets,audit=load_extended();(OUT/'data-audit.json').write_text(json.dumps(audit,indent=2))
(OUT/'protocol.json').write_text(json.dumps({'objective':'Opportunity-universe transfer,not a parameter search','cases':'17ETF source universe(15equityused),and HK5equity subset;each with/without profit pyramids. Same MA entry,longtrendexit,risk0.5%/4% aggregate andcosts as campaign-v2.','limitation':'Current surviving funds,listingvenue not identical to economicexposure;3110 highdividend index strategy changed2025;100unit conservative trades;HK50% newbuy exposurecap retained.'},indent=2))
records=[]
for market in ['mixed','HK']:
 for adds in [False,True]:
  chosen={n:a for n,a in assets.items() if market=='mixed' or a['currency']=='HKD'}
  name=f'{market}-adds{adds}'
  m,p,o,c,s=run_campaign(chosen,entry='ma',exit_mode='trend',pyramid=adds);m['case']=name;records.append(m)
  p.to_csv(OUT/(name+'-path.csv'));(OUT/(name+'-orders.json')).write_text(json.dumps(o));(OUT/'results.json').write_text(json.dumps(records,indent=2))
  print(name,'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'best252',round(m['best252_return']*100,2),flush=True)
