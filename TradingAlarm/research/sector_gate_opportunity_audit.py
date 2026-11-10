"""Gate-pass versus gate-closed entry opportunities, fixed same-date comparisons."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
OUT=Path('results/sector-gate-opportunity-audit')
def match_strength(passed,closed):
    available=closed.sort_values(['strength','symbol']).copy();pairs=[]
    for row in passed.sort_values(['strength','symbol']).itertuples():
        if available.empty:break
        j=(available.strength-row.strength).abs().idxmin();other=available.loc[j]
        pairs.append((row.Index,j));available=available.drop(j)
    return pairs

def main():
 OUT.mkdir(exist_ok=True);label_path=Path('results/sector-admission-outcomes/labels.parquet');score_path=Path('results/broad-exit-disagreement/all-observed-signals.parquet')
 d=pd.read_parquet(label_path);scores=pd.read_parquet(score_path)[['date','symbol','strength']];d=d.merge(scores,on=['date','symbol'],how='left',validate='many_to_one');assert d.strength.notna().all()
 d=d[d.reason.ne('missing_group')].copy();d['passed']=d.reason.isin(['selected','slot_constraints_or_ranking']);assert set(d.reason)=={'selected','slot_constraints_or_ranking','group_gate_closed'}
 protocol={'comparison':'All first-cross opportunities with known proxy group, including unselected gate-pass candidates','horizons':[21,63],'methods':['same-date mean pass-minus-closed','same-date greedy nearest strength without replacement, pass ascending strength then symbol; ties closed ascending strength then symbol'],'aggregation':'Equal date weight within each year/horizon; no outcome used in matching','limitations':['Gate is constant within date/proxy group so same-date same-group gate comparison impossible. Sector composition remains a confounder.','Nearest strength is approximate, greedy and order dependent; report strength gaps; no causal claims.','21/63 observed-close returns are mature evaluation labels, not executable account returns.','No parameter/threshold tuning; all inspected surviving-stock development sample.']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 daily=[];matches=[]
 for (year,h,date),g in d.groupby(['year','horizon','date']):
  a=g[g.passed];b=g[~g.passed]
  if a.empty or b.empty:continue
  row=dict(year=int(year),horizon=int(h),date=str(date.date()),pass_n=len(a),closed_n=len(b))
  for metric in ['forward_return','tail30','tail80','loss30']:row[metric]=float(a[metric].mean()-b[metric].mean())
  daily.append(dict(method='date',**row))
  pairs=match_strength(a,b);diffs=[]
  for i,j in pairs:
   x=d.loc[i];y=d.loc[j];v={metric:float(x[metric])-float(y[metric]) for metric in ['forward_return','tail30','tail80','loss30']};diffs.append(v)
   matches.append(dict(year=int(year),horizon=int(h),date=str(date.date()),pass_symbol=x.symbol,closed_symbol=y.symbol,strength_gap=float(x.strength-y.strength),**v))
  daily.append(dict(method='date_strength',**{k:row[k] for k in ['year','horizon','date','pass_n','closed_n']},**pd.DataFrame(diffs).mean().to_dict()))
 f=pd.DataFrame(daily);m=pd.DataFrame(matches);f.to_csv(OUT/'daily-contrasts.csv',index=False);m.to_csv(OUT/'matches.csv',index=False)
 for _,g in m.groupby(['horizon','date']):assert g.pass_symbol.is_unique and g.closed_symbol.is_unique
 s=f.groupby(['method','year','horizon']).agg(dates=('date','size'),mean_return_difference=('forward_return','mean'),tail30_difference=('tail30','mean'),tail80_difference=('tail80','mean'),loss30_difference=('loss30','mean')).reset_index();s.to_csv(OUT/'summary.csv',index=False)
 report={'status':'development_diagnostic','labeled_rows':len(d),'matches':len(m),'median_abs_strength_gap':float(m.strength_gap.abs().median()),'p95_abs_strength_gap':float(m.strength_gap.abs().quantile(.95)),'summary':s.to_dict('records'),'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [label_path,score_path,Path(__file__)]}}
 (OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(s.to_string(index=False));print('strength gaps median/p95',report['median_abs_strength_gap'],report['p95_abs_strength_gap'])
if __name__=='__main__':main()
