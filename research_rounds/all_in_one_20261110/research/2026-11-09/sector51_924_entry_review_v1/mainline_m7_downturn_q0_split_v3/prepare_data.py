from pathlib import Path
p=Path(__file__).resolve().parent/'engine.py';s=p.read_text();pos=s.index('\ndef q0_guard')
s=s[:pos]+'''
FACT_PATH=O.parent/'retained_605499_split_cash_evidence_v1/Q0_ONLY_EVENT_FACTS.json'
FACT_SHA='f7e7ff5994fbefd843eaf3e378b1ab4b6b2df1baf62f67a9009f4f8c891b962d'
class Data(m7.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  assert sha(FACT_PATH)==FACT_SHA
  self.hashes[str(FACT_PATH)]=FACT_SHA
  records=read(FACT_PATH);assert len(records)==1
  ev=records[0];s=ev['sid'];dt=pd.Timestamp(ev['ex_date'])
  assert s==SID and ev['ex_date']==EX_DATE and ev['record_date']==RECORD_DATE
  assert ev['pay_date']==EX_DATE and ev['new_shares_sellable_at']==EX_DATE
  assert ev['admission_scope']=='ZERO_HOLDING_NEVER_SEEDED_RETAINED_TICKET_ONLY' and ev['held_split_supported'] is False
  assert m7.dec(ev['split_ratio'])==m7.D('1.30') and m7.dec(ev['d_source'])==m7.D('2.50') and ev['d_cash']==ev['d_source']
  paths=dict(ev['evidence_hashes'])
  for stem in ['source_fact','signal','local_action']:paths[ev[stem+'_path']]=ev[stem+'_sha256']
  paths[ev['notice']['pdf_path']]=ev['notice']['pdf_sha256']
  for path,h in paths.items():assert sha(Path(path))==h,('Q0_FACT_DRIFT',path);self.hashes[path]=h
  for path in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_q0.py']:self.hashes[str(path)]=sha(path)
  if dt>self.end:return
  assert (s,dt) not in self.events
  terms=[a for a in self.actions[s]['events'] if a['effective_date']==EX_DATE];assert len(terms)==1
  assert m7.dec(terms[0]['split_ratio'])==m7.dec(ev['split_ratio']) and m7.dec(terms[0]['cash_per_old_share'])==m7.dec(ev['d_source'])
  z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt]
  assert day(prev.name)==RECORD_DATE and m7.m3.valid(prev) and m7.m3.valid(cur)
  assert m7.m3.lineage(prev)==m7.m3.lineage(cur)==tuple(ev['source_lineage'])
  fo=m7.dec(prev.adjustment_factor);fn=m7.dec(cur.adjustment_factor);pc=m7.dec(prev.raw_close)
  assert abs(fo/m7.dec(ev['factor_old'])-1)<m7.D('1e-11') and abs(fn/m7.dec(ev['factor_new'])-1)<m7.D('1e-11')
  assert abs(fo*pc*m7.dec(ev['split_ratio'])/(pc-m7.dec(ev['d_source']))/fn-1)<m7.D('1e-11')
  self.events[(s,dt)]=dict(ev,q0_never_seeded_only=True)
  self.admission.append(dict(sid=s,ex_date=EX_DATE,event_id=ev['economic_event_id_candidate'],status='REVIEWED_Q0_ONLY_SPLIT_CASH',held_split_supported=False,factor_bridge_verified=True,not_PIT=True,not_production_admission=True))
''' +s[pos:]
s=s.replace(" def economic_preflight(self,d,pending):\n  before=q0_guard", " def register_pay(self,d):\n  if day(d)==RECORD_DATE and (SID in self.active or any(k[0]==SID for k in self.claims)):\n   raise Blocked(f'{day(d)} {SID} Q0_SPLIT_RECORD_ENTITLEMENT_FORBIDDEN')\n  return super().register_pay(d)\n def economic_preflight(self,d,pending):\n  balances=(self.cash,self.receivable,copy.deepcopy(self.claims),sum(self.quantity(a) for a in self.active.values()),sum(a['dividend'] for a in self.archive.values()))\n  before=q0_guard")
s=s.replace("  if before is not None:\n   after", "  if before is not None:\n   if balances!=(self.cash,self.receivable,self.claims,sum(self.quantity(a) for a in self.active.values()),sum(a['dividend'] for a in self.archive.values())):raise Blocked(f'{day(d)} {SID} Q0_SPLIT_ENTITLEMENT_MUTATION')\n   after")
s=s.replace("('export','economic_preflight')", "('export','economic_preflight','register_pay')")
s=s.replace("Unchanged frozen M7 endpoint extension. No suspension accounting installed.","Frozen M7 extension with reviewed Q0-only split/cash bridge. No held split or suspension accounting.")
s=s.replace("assert not (O/'RUN_STARTED.json').exists()", "assert read(O/'SYNTHETIC_QA.json')['result']=='PASS'\n  assert not (O/'RUN_STARTED.json').exists()")
p.write_text(s)
