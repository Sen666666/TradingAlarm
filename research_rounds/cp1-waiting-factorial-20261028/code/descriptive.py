"""After-outcome descriptive tables; no trading imports, no parameter changes."""
from fw_common import *
def exclusive_or_identical(path,content):
 if path.exists():assert path.read_text()==content,path
 else:
  with path.open('x') as f:f.write(content)
def main():
 out=O/'comparison';s=pd.read_csv(out/'summary.csv');env=s.groupby(['sector','policy'],sort=False).agg(observed_min_return=('net_return','min'),observed_max_return=('net_return','max'),observed_max_drawdown=('max_drawdown','max')).reset_index();exclusive_or_identical(out/'scenario-envelope.csv',env.to_csv(index=False))
 changes=[]
 for sector in ['TECH','DRUG']:
  for a,b in [('ACP','SCP'),('A3CP','WCP'),('A10CP','W10CP')]:
   for stress in SCENARIOS:
    x=s[s.sector.eq(sector)&s.policy.eq(a)&s.scenario.eq(stress)].iloc[0];y=s[s.sector.eq(sector)&s.policy.eq(b)&s.scenario.eq(stress)].iloc[0]
    r=dict(sector=sector,baseline=a,candidate=b,scenario=stress)
    for k in ['net_return','max_drawdown','tail_profit','ordinary_profit','all_closed_losses','mean_exposure','extended_net']:r['delta_'+k]=float(y[k]-x[k])
    changes.append(r)
 exclusive_or_identical(out/'entry-family-effects.csv',pd.DataFrame(changes).to_csv(index=False))
 for _,r in s.iterrows():
  if r.sector=='TECH' and r.policy in MODES:assert r.tail_profit>r.all_closed_losses
  if r.sector=='DRUG' and r.policy in MODES:assert r.net_return<0
 save(O/'supplementary-verification.json',dict(passed=True,waiting_prefix=read(O/'waiting-prefix-verification.json'),matrix_rows=len(s),main_stock_pnl_decompositions=90,entry_family_descriptive_pairs=len(changes),source_sha256={str(p):sha(p) for p in [Path(__file__),O/'code/case_path.py',O/'code/waiting_prefix.py']},envelope_caveat='Only min/max over three preset historical execution scenarios; neither probabilities nor future return/drawdown bounds.'))
if __name__=='__main__':main()
