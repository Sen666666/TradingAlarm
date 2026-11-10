"""Reuse verified read-only accounting analyzer with explicit source aliases."""
import inspect,json,gzip
from pathlib import Path
import adapter as A
J=A.J;L=A.L;OUT=A.O/'comparison-analysis';BASELINE=J.O/'run-universe';NEW=A.O/'run'
M=J.W.load('single_factor_existing_saved_analyzer',J.O/'analyze_saved.py')
def account_source(path):
 origin=BASELINE if Path(path).name=='A.json.gz' else NEW
 with gzip.open(origin/'pair/B.json.gz','rt') as f:return json.load(f)
def row_source(path):
 # Names A/B are internal analyzer aliases only, not new trading accounts.
 for alias,origin in [('A',BASELINE),('B',NEW)]:
  with gzip.open(origin/'pair'/Path(path).name,'rt') as f:
   for line in f:
    r=json.loads(line)
    if r['account']=='B':yield dict(r,account=alias)
def main():
 OUT.mkdir(exist_ok=True)
 source=inspect.getsource(M.main)
 needle="out=J.O/('run-'+scope);pair=out/'pair';assert L.read(out/'DONE.json')['completed']"
 assert source.count(needle)==1
 source=source.replace(needle,"out=OUT;pair=out/'source_alias_only';assert all(L.read(p/'DONE.json')['completed'] for p in (BASELINE,NEW))")
 env=dict(M.__dict__,gz=account_source,rows=row_source,OUT=OUT,BASELINE=BASELINE,NEW=NEW)
 exec(source,env);env['main']('unused')
 labels={'A':'original_B','B':'B_diag'}
 p=OUT/'SUMMARY.json';summary=L.read(p);summary['metrics']={labels[k]:v for k,v in summary['metrics'].items()};summary['source_aliases']={'A':'original_v3_B','B':'B_diag'};L.save(p,summary)
 meta=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'));names={m['sector_id']:m['industry'] for m in meta.values()}
 for filename in ('SIX_CASES','INDUSTRY_MONEY_CONTRIBUTION','OPPORTUNITY_FUNDING_FUNNEL'):
  p=OUT/(filename+'.json');r=L.read(p)
  for x in r:
   x['account']=labels[x['account']]
   if 'sector' in x:x['industry']=names[x['sector']]
  L.save(p,r)
 L.save(OUT/'SOURCE_MANIFEST.json',dict(analysis_only=True,baseline=str(BASELINE),new_path=str(NEW),original_A_not_used=True,
  raw_trade_values_unmodified=True,internal_aliases=labels,base_analyzer_sha256=L.sha(J.O/'analyze_saved.py'),
  baseline_B_sha256=L.sha(BASELINE/'pair/B.json.gz'),B_diag_sha256=L.sha(NEW/'pair/B.json.gz')))
 print('READONLY_ANALYSIS_DONE')
if __name__=='__main__':main()
