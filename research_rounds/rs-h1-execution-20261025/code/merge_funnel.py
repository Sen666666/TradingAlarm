"""Merge disjoint account diagnostics; each source candidate/day stays once."""
import os,collections
import pandas as pd
from build_inputs import HERE,read,write,ref,now

def main():
 assert read(HERE/'accounts-v2/summary.json').get('completed_accounts')==12
 roots=[HERE/('funnel-v2-'+g) for g in ['G0','G1']]
 assert all((p/'summary.json').exists() for p in roots)
 counts=[read(p/'summary.json')['decision_rows'] for p in roots];assert counts==[17196,17196]
 out=HERE/'funnel-v2';out.mkdir(exist_ok=False)
 rows=[x for p in roots for x in read(p/'target-counters.json')];assert len({(x['account'],x['key']) for x in rows})==len(rows)
 write(out/'target-counters.json',rows);totals={k:v for p in roots for k,v in read(p/'totals.json').items()};assert len(totals)==12
 write(out/'totals.json',totals);pd.concat([pd.read_csv(p/'daily-candidate-counts.csv',keep_default_na=False) for p in roots]).sort_values(['date','account']).to_csv(out/'daily-candidate-counts.csv',index=False,encoding='utf-8-sig')
 assert read(roots[0]/'qualified-annual-top20.json')==read(roots[1]/'qualified-annual-top20.json')
 os.link(roots[0]/'qualified-annual-top20.json',out/'qualified-annual-top20.json')
 write(out/'summary.json',dict(recorded_at=now(),accounts=12,decision_rows=sum(counts),groups=[ref(p/'summary.json') for p in roots],
  main_source=ref(HERE/'accounts-v2/provenance.json'),duplicate_candidate_days=0,counting_unit='candidate/day, not fills or unique trades'))
 print({'decision_rows':sum(counts),'diagnostic_groups':len(rows)},flush=True)

if __name__=='__main__':main()
