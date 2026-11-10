"""Exit mechanism contrasts; sizing changes explicitly labeled risk diagnostics."""
import json,hashlib
from pathlib import Path
from campaign_engine import run_campaign
from sector_factors import expanded_assets
from portfolio_data import ROOT
OUT=ROOT/'results/campaign-v2'
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 cases={'trend_exit_no_add':{'pyramid':False},'trend_exit_add':{},
 'trend_exit_add_cost':{'cost_bps':30,'fx_bps':30},'trend_exit_add_delay':{'extra_delay':2},
 'risk_double_no_add':{'pyramid':False,'risk_fraction':.01,'planned_risk_cap':.08},
 'risk_double_add':{'risk_fraction':.01,'planned_risk_cap':.08}}
 protocol={'cases':cases,'entry':'Same MA200+positive126day momentum as campaign-v1',
 'exit':'Retain initial4ATR stop;stop can move up on actual add fills,not on every new high. Also exit after2closes belowMA200. No fixed profit target.',
 'risk_diagnostic':'Last2 cases double per-entry risk0.5% to1% and planned aggregate stop loss4% to8%;not same-risk alpha comparisons.16% risk-epoch drawdown cash guard unchanged.',
 'hypothesis':'ATR trailing could truncate large trends;test fixed initial protection plus long trend exit,not search exit-window optimum.',
 'status':'Exploratory,all old histories seen;80% account target not guaranteed',
 'engine_sha256':hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest()}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2));records=[];assets=expanded_assets()
 for name,kw in cases.items():
  m,p,o,c,s=run_campaign(assets,entry='ma',exit_mode='trend',**kw);m['case']=name;records.append(m)
  p.to_csv(OUT/(name+'-path.csv'));(OUT/(name+'-orders.json')).write_text(json.dumps(o))
  (OUT/(name+'-campaigns.json')).write_text(json.dumps({'closed':c,'open':s}))
  (OUT/'results.json').write_text(json.dumps(records,indent=2))
  print(name,'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'best252',round(m['best252_return']*100,2),'cash',round(m['average_cash_weight']*100,1),flush=True)
if __name__=='__main__':main()
