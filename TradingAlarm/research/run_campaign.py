import json,hashlib
from pathlib import Path
from sector_factors import expanded_assets
from portfolio_data import ROOT
from campaign_engine import run_campaign
OUT=ROOT/'results/campaign-v1'
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 cases={'breakout_no_add':{'pyramid':False},'breakout_add':{},'ma_no_add':{'entry':'ma','pyramid':False},
        'ma_add':{'entry':'ma'},'ma_add_highcost':{'entry':'ma','cost_bps':30,'fx_bps':30},
        'ma_add_delay':{'entry':'ma','extra_delay':2}}
 protocol={'objective':'Whole account>80% in large trend,20% drawdown research target; no guarantee',
 'cases':cases,'entry':'55day prior-high breakout OR price>SMA200 and126day total return>0',
 'selection':'When cash/slots constrained,rank eligible entries by prior126day return;max4 names',
 'sizing':'Each entry/add planned loss0.5% NAV at4ATR stop;max3 layers,add only after2 entryATR favorable move and above actual prior fill. No fixed profit target;stop is max(previous stop,highest close-4ATR).',
 'limits':'No leverage;new-buy gross90%,single35%,named sector45%,HK50%;planned stop-distance loss4%NAV. Exposure may drift above caps; these are not guaranteed gap-loss limits.',
 'guard':'At10% risk-epoch drawdown halve initial entry risk and forbid adds;at16% close all next available opens;after20 union sessions flat reset risk epoch, never reset reported account peak.',
 'accounting':'Raw shares,dividend receivables paid on pay date,split-effective dates,previous-day FX,board lots,minimum commissions,1% lagged20day ADV,zero-volume no fill.',
 'signal_prices':'Cumulative split multiplier plus cumulative split-adjusted cash dividends, causal additive series. No current-close-dependent factor at order execution.',
 'limitations':['No historical orderbook/limit queue or venue settlement','Delayed stops may gap;profit adds may increase drawdown','Campaign dividend P&L attribution uses exdate FX claim;total account ledger uses payment-date FX and conversion fee','Partial buy fill counts as a layer; no automatic remainder purchase','No untouched test interval;cases exploratory'],
 'source_sha256':hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest()}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 assets=expanded_assets();records=[]
 for name,kw in cases.items():
  m,p,orders,closed,opened=run_campaign(assets,**kw);m['case']=name;records.append(m)
  p.to_csv(OUT/(name+'-path.csv'))
  (OUT/(name+'-orders.json')).write_text(json.dumps(orders))
  (OUT/(name+'-campaigns.json')).write_text(json.dumps({'closed':closed,'open':opened},indent=2))
  (OUT/'results.json').write_text(json.dumps(records,indent=2))
  print(name,'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'best252',round(m['best252_return']*100,2),flush=True)
if __name__=='__main__':main()
