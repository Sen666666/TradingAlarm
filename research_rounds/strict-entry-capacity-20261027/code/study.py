from pathlib import Path
import sys,json,hashlib,inspect,textwrap
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027'
sys.path.insert(0,str(PRIOR/'code'));import experiment as P
E=P.E;R=P.R;A=P.A;pd=P.pd;np=P.np
from dataclasses import replace
from decimal import Decimal as D
STARTS={'S0':'2023-12-29','S1':'2024-06-28','S2':'2024-12-31'};MODES=['A6','S6','A12','S12'];SIGNALS={};LARGE=False
original_override=E.risk_policy.override;original_decide=E.admission.decide
src=inspect.getsource(original_decide)
for a,b in [('len(occupied_issuers) >= 6','len(occupied_issuers) >= 12'),("(6 if variant == 'S1' else 2)","(6 if variant == 'S1' else 4)")]:
 assert src.count(a)==1;src=src.replace(a,b)
ns=dict(E.admission.__dict__);exec(src,ns);decide12=ns['decide']
src2=textwrap.dedent(inspect.getsource(E.ledger.SectorAccount.apply_decision))
for a,b in [("GROSS*bal['nav']/6","GROSS*bal['nav']/12"),('len(occupied) >= 6','len(occupied) >= 12')]:assert src2.count(a)==1;src2=src2.replace(a,b)
ns2=dict(E.ledger.__dict__);exec(src2,ns2);apply12=ns2['apply_decision']
def decide(**kwargs):return (decide12 if LARGE else original_decide)(**kwargs)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def override(a,stocks,clock,mode,Fact):
 global LARGE
 LARGE=a.mode.endswith('12')
 if a.mode.startswith('S'):
  day=pd.Timestamp(clock.decision_at.date());stocks=tuple(replace(s,buy_allowed=Fact(False,clock.decision_at,clock.decision_at,source_id='strict_e0_entry_only')) if day not in SIGNALS[s.security_id].index or not bool(SIGNALS[s.security_id].loc[day,'strict_target']) else s for s in stocks)
 return original_override(a,stocks,clock,mode,Fact)
class Account(E.Account):
 def apply_decision(self,decision,**kwargs):
  self.max_issuers_per_sector=4 if self.mode.endswith('12') else 2
  return (apply12 if self.mode.endswith('12') else E.ledger.SectorAccount.apply_decision)(self,decision,**kwargs)
def setup(cutoff=None):
 global SIGNALS
 old=P.setup('RS');E.risk_policy.override=override;E.admission.decide=decide;R.Account=Account;R.Runner=E.Runner;R.Facts=E.Facts
 SIGNALS={p.stem:pd.read_parquet(p).loc[:cutoff] if cutoff else pd.read_parquet(p) for p in (O/'signals').glob('*.parquet')}
 return old

def run(cohort,stage):
 root=O/cohort;root.mkdir(exist_ok=True);link=root/'execution-rules-v2.json'
 if not link.exists():link.symlink_to((PRIOR/'execution-rules-v2.json').resolve())
 if stage=='economic':assert read(O/'admission.json')['passed'] and (O/'freeze.json').exists()
 end=(pd.Timestamp(STARTS[cohort])+pd.Timedelta(days=75)).date().isoformat() if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27';old=setup(end if stage=='prefix' else None)
 R.run(root/({'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'}[stage]),modes=MODES,stresses=['base','cost2','delay1'] if cohort=='S0' else ['base','delay1'],start=STARTS[cohort],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic');R.context=old
if __name__=='__main__':run(sys.argv[2],sys.argv[1])
