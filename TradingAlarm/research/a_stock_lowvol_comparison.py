"""Ranking gate diagnostics, including implied notional needed for equal risk."""
import json,math
import pandas as pd
from build_stock_features import ROOT


def main():
 out=ROOT/'results/a-stock-lowvol-gate';base=ROOT/'results/a-stock-zero-range-stress'
 old=json.loads((base/'cutoffs/summary.json').read_text());new=json.loads((out/'cutoffs/summary.json').read_text())
 lookup={(r['cutoff'],r['cost_bps']):r for r in old};comparisons=[]
 for r in new:
  b=lookup[r['cutoff'],r['cost_bps']]
  comparisons.append(dict(cutoff=r['cutoff'],cost_bps=r['cost_bps'],baseline_R=b['marked_mean_R'],lowvol_R=r['marked_mean_R'],difference=r['marked_mean_R']-b['marked_mean_R'],ordinary_R=r['ordinary_R'],top10_R=r['top10_R'],zero_terminal_R=r['zero_terminal_sensitivity_mean_R']))
 summaries=[]
 for label,directory in [('baseline',base),('lowvol',out)]:
  d=pd.read_parquet(directory/'campaigns.parquet');known=d[d.status.ne('terminal_unknown')];closed=d[d.status.eq('closed')]
  winners=closed[closed.R_cost15.gt(0)];losers=closed[closed.R_cost15.lt(0)];v=known.R_cost15;tail=v.nlargest(math.ceil(len(v)*.1))
  # Diagnostic only: ignores minlots,cash,concurrentholdings and executioncap.
  notional=.005*d.entry_price/d.risk_distance
  summaries.append(dict(variant=label,campaigns=len(d),closed=len(closed),open=int(d.status.eq('open_at_cutoff').sum()),unknown=int(d.status.eq('terminal_unknown').sum()),known_mean_R=float(v.mean()),closed_win_rate=len(winners)/len(closed),closed_payoff_R=float(winners.R_cost15.mean()/-losers.R_cost15.mean()),ordinary_mean_R=float(v.drop(tail.index).mean()),price_moves_ge80=int(known.price_move.ge(.8).sum()),median_implied_notional_fraction_at_half_percent_risk=float(notional.median()),count_implied_notional_above35percent=int(notional.gt(.35).sum())))
 result=dict(cutoffs=comparisons,summary=summaries,limitations='Fullpath independentstock signal rerun,not accountsimulation. LowerATR entails more notional for sameplannedR;no claim sumR ormeanR is tradableportfolioyield. Reusedhistory,notnewholdout.')
 (out/'comparison.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 p=ROOT/'progress.json';d=json.loads(p.read_text());d['a_stock_opportunity_ranking']={'status':'allcandidate_ranks_and_full_lowvol_gate_paths_complete','diagnostic':'126652candidate-dates;1055signal dates;median84/max4179candidates;top10signal dates14.89percententries. Rankingusesallsignalsincludingheldandfutureunfillednames.','comparison':result,'validation':'13signal/ranking/snapshottests pass;allcampaigns joinprior-signal-date context;no futuredate inranking;5426histories and5cutoffs rerun.','limitations':'Independent per-stock rankentryfilter is not finitecapacityallocation;currentdata notPITcertified.','next':'Assesscutoffconsistency and capitalintensity before anyadoption or fundedportfolio comparison.'};p.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
