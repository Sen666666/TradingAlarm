"""Compare frozen volume hypothesis with identical execution/cost controls."""
import json
import pandas as pd
from build_stock_features import ROOT


def main():
 out=ROOT/'results/a-stock-volume-confirm';base=ROOT/'results/a-stock-zero-range-stress'
 old=json.loads((base/'cutoffs/summary.json').read_text());new=json.loads((out/'cutoffs/summary.json').read_text())
 lookup={(x['cutoff'],x['cost_bps']):x for x in old};rows=[]
 for r in new:
  b=lookup[r['cutoff'],r['cost_bps']]
  rows.append(dict(cutoff=r['cutoff'],cost_bps=r['cost_bps'],baseline_R=b['marked_mean_R'],volume_R=r['marked_mean_R'],difference=r['marked_mean_R']-b['marked_mean_R'],ordinary_R=r['ordinary_R'],tail_R=r['top10_R']))
 summaries=[]
 for name,path in [('baseline',base),('volume',out)]:
  d=pd.read_parquet(path/'campaigns.parquet');k=d[d.status.ne('terminal_unknown')];c=d[d.status.eq('closed')];w=c[c.R_cost15.gt(0)];l=c[c.R_cost15.lt(0)]
  summaries.append(dict(variant=name,campaigns=len(d),closed=len(c),open=int(d.status.eq('open_at_cutoff').sum()),unknown=int(d.status.eq('terminal_unknown').sum()),closed_win_rate=len(w)/len(c),closed_payoff_R=float(w.R_cost15.mean()/-l.R_cost15.mean()),known_mean_R=float(k.R_cost15.mean()),price_moves_ge80=int(k.price_move.ge(.8).sum())))
 result=dict(cutoffs=rows,summary=summaries,limitations='Syntheticprices,notcapitalconstrainedaccount;reusedhistories andoverlappingcutoffs. No parameter search;rawvolumeaffectedbysharechanges.',research_context={'source':'https://www.lsvasset.com/pdf/research-papers/Price-Momentum-Trad-Vol-2000.pdf','interpretation':'Lee/Swaminathan2000 studies turnover and momentum persistence/reversal over longer horizons,not this1day/20dayvolumeconfirmation. It doesnotestablish thathighervolumeisuniversallybetter. Our rule is an explicit independent hypothesis,not a replication.'})
 (out/'comparison.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 p=ROOT/'progress.json';d=json.loads(p.read_text());d['a_stock_reentry_volume']={'status':'reentrydiagnostic_andfullvolumeconfirmation_rerun_complete','reentry':'No evidenceforblindlosscooldown;6-20calendardayreentriesafterloss positive atlatestcutoff. Firstentriesconfoundedbyteststartregime. Diagnosticnotcounterfactual.','comparison':result,'validation':'11signal/cutofftests pass. Full5426histories,sourcepriceparity,and5cutoffreconciliation. Volumeusesonlysignaldateand20priorvalidsessions;doesnotgateexit.','next':'Reviewconsistencyandtailretention;do notadoptfromlatestendpointalone orclaimaccountperformance.'};p.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
