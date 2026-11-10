"""Audit existing price-only campaigns for sparse-winner economics, without refitting."""
import json,math
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT/'results/campaign-low-atr-v1';OUT=ROOT/'results/trend-tail-audit'
def summarize(closed):
 if not closed:return dict(closed=0)
 f=pd.DataFrame(closed).sort_values(['exit_date','id']);p=f.pnl.astype(float);w=p[p>0];l=p[p<0];hold=(pd.to_datetime(f.exit_date)-pd.to_datetime(f.entry_date)).dt.days
 n=max(1,math.ceil(len(f)*.1));tail=p.nlargest(n);ordinary=p.drop(tail.index);streak=maxstreak=0
 for value in p:
  streak=streak+1 if value<0 else 0;maxstreak=max(maxstreak,streak)
 return dict(closed=len(f),win_rate=float((p>0).mean()),average_win=float(w.mean()) if len(w) else None,average_loss=float(-l.mean()) if len(l) else None,payoff_ratio=float(w.mean()/-l.mean()) if len(w) and len(l) else None,profit_factor=float(w.sum()/-l.sum()) if len(l) else None,closed_pnl=float(p.sum()),largest_winner_pnl=float(p.max()),top10_count=n,top10_pnl=float(tail.sum()),ordinary_pnl=float(ordinary.sum()),ordinary_mean=float(ordinary.mean()) if len(ordinary) else None,top10_share_of_gross_wins=float(tail.clip(lower=0).sum()/w.sum()) if len(w) else None,median_holding_calendar_days=float(hold.median()),median_winner_holding_calendar_days=float(hold[p>0].median()) if len(w) else None,max_consecutive_closed_losses=maxstreak,closed_return_on_total_buy_cash_over30pct=int((p/f.buy_cash>.3).sum()))
def main():
 OUT.mkdir(exist_ok=True)
 protocol=dict(objective='Test sparsepositive-tail economics, not maximizeannualreturn orwinrate',scope='All6previously saved A/HK/mixed ETFcampaign cases, unchanged rules and selections; not newoutofsampletest',definitions='Top10% of closedcampaigns ranked by net campaignPnL, ex-post diagnostic only, never entryselection. Ordinary remainder includes all otherwins/losses. Tradeprofit/buycash not accountreturn orRmultiple.',limitations=['Open campaigns censored;closedonly mayomit currentbigwinners','CampaignPnLincludes entry/exitfees anddividendclaims;HKdividendFXtiming maynot exactlyreconcileaccountNAV','Different asset/position sizes mean cashpayoffratio isnot normalizedR','Sparsewinnerconcentration alone isnot positiveexpectancy;ordinarylosses mayexceedtailgains','ETFpilot selectedsurvivors,not individualstocks/futures/physicalrealestate validation'])
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2));results=[];metrics=json.loads((SOURCE/'results.json').read_text())
 for m in metrics:
  case=m['case'];d=json.loads((SOURCE/f'{case}-campaigns.json').read_text());a=summarize(d['closed']);assert abs(a['top10_pnl']+a['ordinary_pnl']-a['closed_pnl'])<1e-6
  a.update(case=case,open_campaigns=len(d['open']),account_total_return=m['total_return'],account_max_drawdown=m['max_drawdown']);results.append(a)
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results)[['case','closed','open_campaigns','win_rate','payoff_ratio','profit_factor','top10_pnl','ordinary_pnl','closed_pnl','median_holding_calendar_days','median_winner_holding_calendar_days']].to_string(index=False))
if __name__=='__main__':main()
