from pathlib import Path
P=Path(__file__).resolve().parent
B=P.parent/'joint51_candidate_v4_facts/engine.py'
s=B.read_text()
alloc=s[s.index(' def alloc_open('):s.index(' def close(')]
def replace(a,b):
 global alloc
 assert alloc.count(a)==1,(a,alloc.count(a));alloc=alloc.replace(a,b)
replace("  reserved=[]", "  reserved=[]\n  intended={(x['sid'],x['event']):x for x in self._intent_candidates}\n  self._reservation_start=len(self.reservations)")
replace("   caps={'attempt_budget':budget", "   original=intended[(s,r['kind'])]\n   if original['decision']!='PASS':reason=original['decision']\n   caps={'attempt_budget':budget")
replace("min(r['planned_q'],r['capacity']))", "min(r['planned_q'],r['capacity'],original['executed_q']))")
replace("   cost=q*p+self.d.fee(s,d,q,p,'buy');cash-=cost;sec[self.d.sid_sector[s]]+=cost;sv[s]=sv.get(s,ZERO)+cost;reserved.append((r,q,p,net,cost))", "   assert q<=original['executed_q'],('INTENT_Q_INCREASE',s,q,original)\n   cost=q*p+self.d.fee(s,d,q,p,'buy');before=cash;cash-=cost;sec[self.d.sid_sector[s]]+=cost;sv[s]=sv.get(s,ZERO)+cost\n   self.reservations.append(dict(day=day(d),sid=s,kind=r['kind'],rank=rank+1,original_q=original['executed_q'],reserved_q=q,reserved_cost=str(cost),cash_before=str(before),cash_after=str(cash),cp_id=r.get('cp_id')))\n   row['original_intended_q']=original['executed_q'];row['reserved_q']=q;reserved.append((r,q,p,net,cost,row))")
replace("  for r,q,p,net,cost in reserved:\n   s=r['sid']", "  for r,q,p,net,cost,row in reserved:\n   s=r['sid']\n   if self.no_fill(s,d):\n    row['decision']='NO_FILL_ONEPRICE_EXPOST';row['executed_q']=0;row['fill_status']='NO_FILL';self.record_nofill(d,s,'BUY_'+r['kind'],q,p,signal_day=r['signal_day'],cp_id=r.get('cp_id'),round_id=self.active[s]['id'] if s in self.active else None,reserved_cost=str(cost));continue\n   row['fill_status']='FILLED'")
header='''"""Independent daily one-price execution scenario. No changes to source artifacts."""
from pathlib import Path
import importlib.util,os,sys,json,hashlib,copy,argparse,ast
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
FACTS=Path(os.environ.get('STRESS_FACTS',str(ROOT.parent/'joint51_candidate_v4_facts')))
spec=importlib.util.spec_from_file_location('frozen_baseline',FACTS/'engine.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
D=b.D;ZERO=b.ZERO;INITIAL=b.INITIAL;SLIP=b.SLIP;pd=b.pd;np=b.np;dec=b.dec;day=b.day;finite=b.finite;lineage=b.lineage;Blocked=b.Blocked;defaultdict=b.defaultdict;read=b.read;save=b.save;sha=b.sha
class StressEngine(b.Engine):
 def __init__(self,data,gate=True):
  super().__init__(data);self.gate=gate;self.nofills=[];self.intents=[];self.reservations=[]
 def no_fill(self,s,d):
  if not self.gate:return False
  z=self.d.z(s,d);keys=['raw_open','raw_high','raw_low','raw_close']
  if not all(finite(z.get(k)) and z[k]>0 for k in keys):raise Blocked(f'{day(d)} {s} ONEPRICE_GATE_OHLC_MISSING')
  return len({dec(z[k]) for k in keys})==1
 def record_nofill(self,d,s,side,q,p,**kw):
  self.nofills.append(dict(day=day(d),sid=s,side=side,qty=q,proxy_price=str(p),reason='EXPOST_RAW_OHLC_EQUAL',**{k:str(self.d.z(s,d)[k]) for k in ['raw_open','raw_high','raw_low','raw_close']},**kw))
 def freeze_intent(self,d,pending):
  shadow=b.Engine(self.d)
  state=copy.deepcopy({k:v for k,v in self.__dict__.items() if k not in ['d','_intent_candidates','_intent_orders','_reservation_start']})
  shadow.__dict__.update(state);ni=len(shadow.orders);nc=len(shadow.candidates)
  shadow.exit_open(d);shadow.alloc_open(d,copy.deepcopy(pending))
  self._intent_orders=shadow.orders[ni:];self._intent_candidates=shadow.candidates[nc:]
  self.intents.extend([dict(row_type='ORDER',**x) for x in self._intent_orders]+[dict(row_type='ALLOCATION',**x) for x in self._intent_candidates])
 def exit_open(self,d):
  for s,a in sorted(list(self.active.items())):
   z=self.d.z(s,d);px=dec(z['raw_open']);adj=px*a['factor'];self.invalidate_cp(a,d,'OPEN','raw_open')
   if adj<=a['ifloor']:a['exit']='I_OPEN_PROTECTION'
   exiting=[]
   for l in a['lots']:
    if a['exit'] or l.get('exit') or (l['kind']=='ADD' and adj<=l['floor']):
     if d>pd.Timestamp(l['bought']):exiting.append(l)
     else:l['exit']='T1_LOCKED_EXIT'
   if exiting:
    q=sum(l['q'] for l in exiting);reason=a['exit'] or 'CP_LAYER_EXIT';side='SELL_ALL' if q==self.quantity(a) else 'SELL_LAYERS';a['plan']=None
    if self.no_fill(s,d):
     for l in exiting:l['exit']=l.get('exit') or 'ONEPRICE_UNFILLED_LOCKED_EXIT'
     self.record_nofill(d,s,side,q,px*(1-SLIP),round_id=a['id'],lots=[l['id'] for l in exiting],exit_reason=reason)
    else:
     self.order(a,d,side,q,px*(1-SLIP),reason,lots=[l['id'] for l in exiting]);a['lots']=[l for l in a['lots'] if l not in exiting]
   if not self.quantity(a):a['exit_day']=day(d);self.active.pop(s)
'''
footer='''
 def run(self,checkpoints=(),prior=None):
  pending=[];prior_end=None
  if prior:prior_end=read(prior/'DAY_LEDGER.json')[-1]['day']
  for dt in self.d.days:
   prev=self.d.cal[self.d.cal.get_loc(dt)-1]
   keys=['cash','receivable','active','archive','seq','claims','snapshots'];snap=copy.deepcopy({k:getattr(self,k) for k in keys})
   logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','nofills','intents','reservations'];lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(dt,pending);self.accrue(dt);self.freeze_intent(dt,pending);self.exit_open(dt);self.alloc_open(dt,pending);pending=self.close(dt,prev)
    self.pending=pending
    if day(dt) in checkpoints or day(dt)==prior_end:
     dest=self.output_root/('checkpoint_'+day(dt).replace('-',''));self.export(dest)
     if day(dt)==prior_end:
      families=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','OPEN_INTENTS','OPEN_RESERVATIONS','NO_FILLS']
      counts={}
      for name in families:
       assert read(prior/(name+'.json'))==read(dest/(name+'.json')),('STRESS_PREFIX_DRIFT',name);counts[name]=len(read(dest/(name+'.json')))
      save(self.output_root/'PRIOR_PREFIX_REPLAY_QA.json',dict(result='PASS',through=prior_end,exact_rows=counts))
     print('CHECKPOINT '+json.dumps(self.ledger[-1]),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(dt),reason=str(ex),partial_orders=self.orders[lengths['orders']:])
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    self.blockers.append(str(ex));break
  self.pending=pending;return self
 def export(self,path):
  super().export(path)
  for name,rows in [('OPEN_INTENTS',self.intents),('OPEN_RESERVATIONS',self.reservations),('NO_FILLS',self.nofills)]:
   save(path/(name+'.json'),rows);pd.DataFrame(rows).to_csv(path/(name+'.csv'),index=False)
  save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
def economic_ast(path):
 tree=ast.parse(Path(path).read_text());result={}
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):result[node.name]=ast.dump(node,include_attributes=False)
  elif isinstance(node,ast.ClassDef):
   for f in node.body:
    if isinstance(f,ast.FunctionDef) and not(node.name=='Engine' and f.name=='run'):result[node.name+'.'+f.name]=ast.dump(f,include_attributes=False)
 return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['test','freeze','run'],required=True);ap.add_argument('--output');ap.add_argument('--prior');ap.add_argument('--gate-off',action='store_true');args=ap.parse_args()
 if args.mode=='test':
  from synthetic_stress import run
  result=run();save(ROOT/'SYNTHETIC_QA.json',result);print(json.dumps(result,ensure_ascii=False))
 elif args.mode=='freeze':
  out=ROOT/args.output;out.mkdir(exist_ok=False)
  assert read(ROOT/'SYNTHETIC_QA.json')['result']=='PASS'
  original=ROOT.parent/'joint51_candidate_v4_facts/engine.py';assert economic_ast(original)==economic_ast(FACTS/'engine.py'),'FACT_VERSION_CHANGED_ECONOMICS'
  frozen=read(FACTS/'FREEZE.json');assert all(sha(p)==h for p,h in frozen['hashes'].items())
  d=b.Data();assert d.hashes==frozen['hashes']
  own={str(ROOT/n):sha(ROOT/n) for n in ['FROZEN_EXECUTION_CONTRACT.md','stress_engine.py','synthetic_stress.py','SYNTHETIC_QA.json']}
  save(out/'FREEZE.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),no_scenario_outcome_run=True,source_facts=str(FACTS),source_freeze_sha256=sha(FACTS/'FREEZE.json'),source_hashes=d.hashes,scenario_hashes=own,gate_enabled=not args.gate_off))
  print('FROZEN',str(out),len(d.hashes))
 else:
  out=ROOT/args.output;f=read(out/'FREEZE.json');assert f['gate_enabled']==(not args.gate_off);assert f['source_facts']==str(FACTS)
  assert all(sha(p)==h for p,h in {**f['source_hashes'],**f['scenario_hashes']}.items())
  d=b.Data();assert d.hashes==f['source_hashes'];e=StressEngine(d,not args.gate_off);e.output_root=out
  e.run(checkpoints=['2024-09-23','2024-09-25'],prior=Path(args.prior) if args.prior else None);e.export(out/'full_20241031_once')
  status=dict(scope='CONDITIONAL_EXPOST_SCENARIO_NOT_LIVE_EXECUTION_OR_RETURN_BOUND',certified_through=e.ledger[-1]['day'] if e.ledger else None,days=len(e.ledger),orders=len(e.orders),no_fills=len(e.nofills),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None)
  save(out/'RUN_STATUS.json',status);print(json.dumps(status,ensure_ascii=False))
'''
(P/'stress_engine.py').write_text(header+alloc+footer)
print('Created',P/'stress_engine.py')
