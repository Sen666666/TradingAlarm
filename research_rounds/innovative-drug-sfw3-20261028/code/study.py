from drug_common import *
from decimal import Decimal as D
sys.path.insert(0,str(COMBO/'code'));Q=C.import_path('frozen_sfw3_implementation',COMBO/'code/study.py')
STARTS={'S0':'2023-12-29','S1':'2024-06-28','S2':'2024-12-31'};MODES=['I','ACT','S','F','SF','SW3F','BH']
original_step=E.risk_policy.step
base_context=R.context

def override(a,stocks,clock,mode,Fact):
 if a.mode in ['I','BH']:return stocks
 if a.mode in ['ACT','S','F','SF']:return Q.control_override(a,stocks,clock,mode,Fact)
 return Q.override(a,stocks,clock,mode,Fact)
def step(a,at,mode):return original_step(a,at,'CONTROL' if a.mode in ['I','BH'] else mode)
def context(cutoff=None,ids=None):return base_context(cutoff,ids or read(POOL)['groups']['DRUG'])
def setup(root,cutoff=None,technical_control=False):
 old=P.setup('RS');R.Account=Q.Account;R.Runner=E.Runner;R.Facts=E.Facts;E.risk_policy.override=override;E.risk_policy.step=step
 if technical_control:
  R.HERE=root;Q.FAST={p.stem:pd.read_parquet(p) for p in (FREF/'signals').glob('*.parquet')};Q.STRICT={p.stem:pd.read_parquet(p) for p in (SREF/'signals').glob('*.parquet')}
 else:
  R.CORE=PREP;R.PREP=PREP;R.HERE=root;E.PREP=PREP;R.context=context;E.risk_policy.RECOVERY=pd.read_csv(PREP/'recovery.csv',index_col=0,parse_dates=True).loc[:cutoff]
  Q.FAST={p.stem:pd.read_parquet(p).loc[:cutoff] for p in (PREP/'fast').glob('*.parquet')};Q.STRICT={p.stem:pd.read_parquet(p).loc[:cutoff] for p in (PREP/'strict').glob('*.parquet')}
 Q.SESS=sorted({pd.Timestamp(x[:10]) for x in read(PRIOR/'execution-rules-v2.json')['decision_cutoffs']}|{pd.Timestamp(d) for d in ['2023-12-29','2026-10-23','2026-10-26','2026-10-27']})
 return old

def run(c,stage):
 root=O/c;root.mkdir(exist_ok=True);link=root/'execution-rules-v2.json'
 if not link.exists():link.symlink_to(PRIOR/'execution-rules-v2.json')
 if stage=='economic':assert read(O/'admission.json')['passed'] and (O/'freeze.json').exists()
 end=(pd.Timestamp(STARTS[c])+pd.Timedelta(days=75)).date().isoformat() if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27';old=setup(root,end if stage=='prefix' else None)
 R.run(root/({'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'}[stage]),modes=MODES if c=='S0' else ['ACT','SW3F'],stresses=['base','cost2','delay1'] if c=='S0' else ['base','delay1'],start=STARTS[c],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic');R.context=old

def controls():
 root=O/'technical/tech-control';root.mkdir(parents=True);(root/'execution-rules-v2.json').symlink_to(PRIOR/'execution-rules-v2.json');setup(root,technical_control=True)
 R.run(root/'accounts',modes=['ACT','SF','SW3F'],stresses=['base'],start='2023-12-29',end='2024-03-13',technical=True)
 import gzip
 def rows(p):
  with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
 refs={(r['account'],r['at']):r for r in rows(COMBO/'RS/S0/accounts-v2/daily.jsonl.gz')};new=rows(root/'accounts/daily.jsonl.gz');fields=['available','inventory','nav','fees_cny','positions','pending_buys','pending_sells','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable']
 for r in new:
  for k in fields:assert r[k]==refs[r['account'],r['at']][k],(r['account'],r['at'],k)
 end=max(r['at'] for r in new)
 for p in (root/'accounts').glob('*__S0_base.json'):assert read(p)['fills']==[r for r in read(COMBO/'RS/S0/accounts-v2'/p.name)['fills'] if r['at']<=end]
 save(O/'technical-control.json',{'passed':True,'old_tech_controls':3,'daily_rows':len(new),'fills_exact':True,'unchanged_rule_adapter':True})
if __name__=='__main__':controls() if sys.argv[1]=='controls' else run(sys.argv[2],sys.argv[1])
