from pathlib import Path
import ast
O=Path(__file__).resolve().parent;R=O.parent
source=(R/'mainline_candidate_v1/engine.py').read_text();tree=ast.parse(source);cl=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Engine')
def method(name):
 n=next(n for n in cl.body if isinstance(n,ast.FunctionDef) and n.name==name)
 return '\n'.join(source.splitlines()[n.lineno-1:n.end_lineno])+'\n'
header='''"""M3: single combined core-reference hypothesis, not a single-factor ablation."""
from pathlib import Path
import sys,importlib.util,copy,json,inspect,ast,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;V2=ROOT/'mainline_candidate_v2_pending_quote_pause'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
m2=module('m3_frozen_m2',V2/'engine.py');v1=m2.v1;b=v1.b
D=v1.D;ZERO=v1.ZERO;INITIAL=v1.INITIAL;SLIP=v1.SLIP;pd=v1.pd;np=v1.np;dec=v1.dec;day=v1.day;finite=v1.finite;truth=v1.truth;false=v1.false;valid=v1.valid;lineage=v1.lineage;sha=v1.sha;save=v1.save;read=v1.read;Blocked=v1.Blocked;sha_text=v1.sha_text;trigger=v1.trigger
assert sha(V2/'engine.py')=='21434c3c5ab54c5aeac247a4893edad707c848dfc7f02b3b78c7a224531452cb'
# A local namespace reuses unchanged D functions, changing exactly capital-retention allowed keys.
import types
rules=types.ModuleType('m3_reference_rules');sys.modules[rules.__name__]=rules;exec(compile((ROOT/'allocation_ablation_v1/allocation_rules.py').read_text().replace("{'cash_reserve', 'sector_cap'}","{'cash_reserve', 'reference_cap'}"),str(ROOT/'allocation_ablation_v1/allocation_rules.py'),'exec'),rules.__dict__)

def water(lower,es,budget):
 if budget<sum(lower.values(),ZERO):return {},None,'INFEASIBLE_LOWER_EXCEEDS_BUDGET'
 if not es:return {},None,'NO_POSITIVE_E_M'
 lo=ZERO;hi=max(ZERO,budget)/sum(es.values(),ZERO)+max(lower[s]/es[s] for s in es)
 for _ in range(180):
  mid=(lo+hi)/2
  if sum((max(lower[s],mid*es[s]) for s in es),ZERO)>budget:hi=mid
  else:lo=mid
 targets={s:max(lower[s],lo*es[s]) for s in es};total=sum(targets.values(),ZERO);assert abs(total-budget)<=D('1e-18')*max(D(1),abs(budget));assert all(targets[s]>=lower[s] for s in es)
 return targets,lo,'PASS'

class Data(m2.Data):
 def __init__(self,end='2024-10-08'):
  super().__init__(end)
  supplement=ROOT/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_300870_V1.json'
  assert sha(supplement)=='8b575ede04d12775e518216e9be498bb985d4d6b6c0c165f308c09146c291bad'
  self.hashes[str(supplement)]=sha(supplement)
  for e in read(supplement):
   s=e['sid'];dt=pd.Timestamp(e['ex_date'])
   if dt>self.end:continue
   assert (s,dt) not in self.events
   paths=dict(e.get('evidence_hashes',{}))
   for stem in ['source_fact','local_action','signal']:
    if e.get(stem+'_path'):paths[e[stem+'_path']]=e[stem+'_sha256']
   if e.get('notice',{}).get('pdf_path'):paths[e['notice']['pdf_path']]=e['notice']['pdf_sha256']
   for p,h in paths.items():assert sha(Path(p))==h;self.hashes[p]=h
   terms=[x for x in self.actions[s]['events'] if x['effective_date']==e['ex_date']];assert len(terms)==1 and dec(terms[0]['split_ratio'])==1 and dec(terms[0]['cash_per_old_share'])==dec(e['d_source'])
   z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt];fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);pc=dec(prev.raw_close)
   assert lineage(prev)==lineage(cur) and abs(fo*pc/(pc-dec(e['d_source']))/fn-1)<D('1e-11')
   assert pd.Timestamp(e['record_date'])==prev.name and pd.Timestamp(e['record_date'])<dt<=pd.Timestamp(e['pay_date'])
   assert abs(fo/dec(e['factor_old'])-1)<D('1e-11') and abs(fn/dec(e['factor_new'])-1)<D('1e-11') and dec(e['d_cash'])>=0
   self.events[(s,dt)]=dict(e,factor_old=str(fo),factor_new=str(fn));self.admission.append(dict(sid=s,sector51=self.sid_sector[s],ex_date=day(dt),event_id=e['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))
  calendar_path=b.R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet';self.cal=pd.read_parquet(calendar_path,columns=[]).index;self.hashes[str(calendar_path)]=sha(calendar_path)
  for p in [O/'engine.py',O/'CONTRACT.md']:self.hashes[str(p)]=sha(p)

class Engine(m2.Engine):
 def __init__(self,data):
  super().__init__(data);self.reference={};self.reference_log=[];self.capital_lots=[];self.reference_requests=[];self._ref_spent={}
'''
close=method('close').replace('min(int(cap),self.quantity(a))','int(cap)')
noncash=method('noncash').replace("min(r['planned_q'],r['capacity'],self.quantity(a))","min(r['planned_q'],r['capacity'])")
alloc=method('alloc_open').replace("min(q,r['planned_q'],self.quantity(a))","min(q,r['planned_q'],r.get('_ref_q',q))")
alloc=alloc.replace("self.info_open(d);nav=", "self._ref_spent={};self.info_open(d);nav=")
alloc=alloc.replace("caps=dict(x['caps'],cash_reserve=max(ZERO,cash-D('.10')*nav))", "caps=dict(x['caps'],cash_reserve=max(ZERO,cash-D('.10')*nav),reference_cap=self.reference_cap(r,sv))")
alloc=alloc.replace("rules.retry_open_outcome", "rules.retry_open_outcome").replace("cash-=cost;sv[s]=", "cash-=cost;self._ref_spent[self.d.sid_sector[s]]=self._ref_spent.get(self.d.sid_sector[s],ZERO)+cost;sv[s]=")
alloc=alloc.replace("violated_caps=violated,**", "violated_caps=violated,reference_close_q=r.get('_ref_q'),reference_close_rank=r.get('_ref_rank'),**")
alloc=alloc.replace("self.ticket_event(t,d,'OPEN_OUTCOME'","self.pause_unknown_ticket(t,r,reason);self.ticket_event(t,d,'OPEN_OUTCOME'")
alloc=alloc.replace("self.tickets[s]=t;self.ticket_event(t,d,'CAPITAL_REJECT_RETAINED'","self.tickets[s]=t;self.pause_unknown_ticket(t,r,reason);self.ticket_event(t,d,'CAPITAL_REJECT_RETAINED'")
# Non-M UNKNOWN admissions must pause, not masquerade as probes. Reference zero accomplishes capital retention; no CP expansion.
(O/'engine.py').write_text(header+close+noncash+alloc+'\n'+(O/'methods.py.part').read_text())
