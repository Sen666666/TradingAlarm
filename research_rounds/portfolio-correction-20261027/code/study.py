from pathlib import Path
import sys,json,hashlib,inspect,textwrap
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027';ROT=ROOT/'research_rounds/pvr-rotation-20261027-v2'
sys.path.insert(0,str(PRIOR/'code'));import experiment as P
rot=P.C.import_path('correction_pair_execution',ROT/'code/study.py')
E=P.E;R=P.R;A=P.A;pd=P.pd;np=P.np
from dataclasses import replace
from decimal import Decimal as D
from bisect import bisect_right
from model import evidence,perturb,gap_ok
STARTS={'S0':'2023-12-29','S1':'2024-06-28','S2':'2024-12-31'}
MODES=[v+str(i) for v in ['ACT','BUF','COR'] for i in range(3)]
START=None;FIRST=[];WEEKS=set();SIGNALS={}
original_override=E.risk_policy.override

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)

def override(a,stocks,clock,mode,Fact):
 if clock.decision_at.date().isoformat() in FIRST:stocks=perturb(stocks,clock,int(a.mode[-1]),E.admission)
 return original_override(a,stocks,clock,mode,Fact)

class Account(rot.Account):
 pass

class Runner(rot.Runner):
 def start_pair(self,a,at,clock,stocks,sectors):
  strategy=a.mode[:-1]
  if a.swap:
   z=a.swap
   if z['phase']=='sell' and (z['candidate'] in a.buys or a.quantity(z['candidate'])):self.stop_pair(a,at,'ordinary_buy_superseded')
   return
  day=at.date().isoformat()
  if strategy=='ACT' or day in FIRST or day not in WEEKS or not a.risk_state['on']:return
  sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};eligible={sid:E.admission.eligibility(s,ss,clock,'S0') for sid,s in sd.items()}
  ids=[sid for sid,e in eligible.items() if e.q is True and not a.quantity(sid) and sid not in a.buys and sid not in a.exits]
  priority=E.admission._priority(ids,sd,ss,eligible,clock,'S0',[],'correction');marks=self.market.marks(at,a.positions)
  for new in priority:
   a.counts['rotation_candidate_checks']+=1
   if E.projected(a,new,stocks,sectors,clock,marks) is not None:continue
   T=pd.Timestamp(day);nf=SIGNALS[new].loc[T] if T in SIGNALS[new].index else None
   if strategy=='COR' and (nf is None or not bool(nf.new_ok)):a.counts['cor_new_evidence_reject']+=1;continue
   ns=sd[new].rank.read(clock) if sd[new].rank else None;feasible=[]
   for old,pos in a.positions.items():
    if old in a.buys or old in a.exits or any(l.sellable_at>clock.earliest_execution_at for l in pos.lots):continue
    buys=[f.at for f in a.fills if f.security_id==old and f.side=='buy'];sells=[f.at for f in a.fills if f.security_id==old and f.side=='sell'];lastsell=max(sells) if sells else None
    episode=[t for t in buys if lastsell is None or t>lastsell]
    if not episode:continue
    age=sum(min(episode)<=t<=at for t in self.market.sessions['A'])
    if age<10:a.counts['cor_min_hold_reject']+=1;continue
    os=sd[old].rank.read(clock) if sd[old].rank else None
    if not gap_ok(ns,os):continue
    of=SIGNALS[old].loc[T] if T in SIGNALS[old].index else None
    if strategy=='COR' and (of is None or not bool(of.weak)):a.counts['cor_healthy_hold_protected']+=1;continue
    budget=E.projected(a,new,stocks,sectors,clock,marks,remove=old)
    if budget is not None:feasible.append((os,old,budget,age))
   if not feasible:continue
   os,old,budget,age=min(feasible);q=self.market.quote(new,at);support=self.facts.floor(new,at,'I');cap=q.quantity.buy_floor(int(budget/q.raw_price)) if q else 0
   if not cap or support is None:continue
   a.swap_seq+=1;j=bisect_right(self.market.sessions['A'],at)
   z=dict(id=f'CORRECT:{a.swap_seq}:{at.date()}',phase='sell',candidate=new,victim=old,signal_at=at,budget=budget,candidate_score=ns,victim_score=os,score_gap=ns-os,sell_deadline=self.market.sessions['A'][j+1].date().isoformat(),intent_valid=True,strategy=strategy,held_observations=age)
   a.swap=z;a.swap_context=dict(signal_at=at,support=support,nav=a.current_nav,share_cap=cap);a.request_exit(self.market.quote(old,at),clock);a.exits[old].purpose='rotation_exit'
   a.log('rotation_started',at,rotation=dict(z));a.log('same_day_rotation_contract',at,rotation_id=z['id'],**a.swap_context);a.counts['rotation_started']+=1;return

def setup(cohort,cutoff=None):
 global START,FIRST,WEEKS,SIGNALS
 START=STARTS[cohort];orig=P.setup('RS');E.risk_policy.override=override;rot.ENABLED=True;rot.PAIRED_BPS=None;R.Account=Account;R.Runner=Runner;R.Facts=E.Facts
 days=sorted({d[:10] for d in read(PRIOR/'execution-rules-v2.json')['decision_cutoffs']}|{'2023-12-29','2026-10-27'});days=[d for d in days if d>=START];FIRST=days[:5];seen=set();WEEKS=set()
 for d in days:
  dt=pd.Timestamp(d);wk=(dt.isocalendar().year,dt.isocalendar().week)
  if wk not in seen:WEEKS.add(d);seen.add(wk)
 SIGNALS={p.stem:pd.read_parquet(p).loc[:cutoff] if cutoff else pd.read_parquet(p) for p in (O/'signals').glob('*.parquet')}
 return orig

def run(cohort,stage):
 assert cohort in STARTS;root=O/cohort;root.mkdir(exist_ok=True)
 if not (root/'execution-rules-v2.json').exists():(root/'execution-rules-v2.json').symlink_to((PRIOR/'execution-rules-v2.json').resolve())
 if stage=='economic':assert read(O/'admission.json')['passed'] and read(O/'graph-review.json')['reviewed'] and (O/'freeze.json').exists()
 end=(pd.Timestamp(STARTS[cohort])+pd.Timedelta(days=100)).date().isoformat() if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27';orig=setup(cohort,end if stage=='prefix' else None)
 stages={'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'};stress=['base','cost2','delay1'] if cohort=='S0' else ['base','delay1']
 R.run(root/stages[stage],modes=([m for m in MODES if m.endswith('0')] if stage=='prefix' else MODES),stresses=stress,start=STARTS[cohort],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic');R.context=orig

def freeze():
 assert read(O/'admission.json')['passed'] and read(O/'graph-review.json')['reviewed']
 fs=[O/'protocol.json',O/'input.json',O/'graph-review.json',O/'signal-validation.json',O/'tests.json',PRIOR/'freeze.json',ROT/'freeze.json',*sorted((O/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py')),*sorted((ROT/'code').glob('*.py'))]
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(p):sha(p) for p in fs},'signals':{str(p):sha(p) for p in sorted((O/'signals').glob('*.parquet'))}})
if __name__=='__main__':freeze() if sys.argv[1]=='freeze' else run(sys.argv[2],sys.argv[1])
