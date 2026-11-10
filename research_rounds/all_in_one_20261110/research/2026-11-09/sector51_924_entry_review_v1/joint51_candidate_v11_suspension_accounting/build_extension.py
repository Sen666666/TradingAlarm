from pathlib import Path
import hashlib
N=Path(__file__).resolve().parent;old=N.parent/'joint51_candidate_v9_facts'
s=(old/'engine.py').read_text()
s=s.replace("O/'FACT_REVISION.json']:hashed(p)","O/'FACT_REVISION.json',O/'SUSPENSION_POLICY.json',O/'synthetic_suspension.py',O/'build_extension.py']:hashed(p)")
needle="  core=pd.read_csv(hashed(P/'CORE_DAILY_51CLASS_SIGNALS.csv'),parse_dates=['day']);core=core[core.day<=self.end]"
insert='''  self.suspension_policy=read(hashed(O/'SUSPENSION_POLICY.json'));pol=self.suspension_policy
  for stem in ['source','official_notice','official_text','fact_envelope']:checked(pol[stem+'_path'],pol[stem+'_sha256'])
  assert not pol['future_notices_or_resume_date_used_for_decisions']
  s=pol['sid'];anchor=self.z(s,pd.Timestamp(pol['mark_source_day']))
  assert valid(anchor) and dec(anchor['raw_close'])==dec(pol['raw_mark']) and dec(anchor['adjustment_factor'])==dec(pol['factor'])
  pol['origin']=lineage(anchor)
  for ds in pol['covered_dates']:
   dt=pd.Timestamp(ds);assert ds>=pol['known_from_date'] and dt>pd.Timestamp(pol['mark_source_day'])
   assert dt not in self.raw[s].index,('UNEXPECTED_OBSERVED_ROW_IN_SUSPENSION',s,ds)
   assert self.stock.at[dt,s]==-1,('SUSPENDED_STOCK_STATE_NOT_UNKNOWN',s,ds)
'''
assert needle in s;s=s.replace(needle,insert+needle)
s=s.replace(" def z(self,s,d):return", " def suspension(self,s,d):\n  p=self.suspension_policy\n  return p if s==p['sid'] and day(d) in p['covered_dates'] else None\n def z(self,s,d):return",1)
s=s.replace('self.blockers=[];self.sector_daily=[]','self.blockers=[];self.sector_daily=[];self.suspension_log=[];self.preflight_log=[]')
a=s.index(' def qvalue(');b=s.index(' def nav(',a)
s=s[:a]+''' def suspension(self,s,d):return self.d.suspension(s,d) if hasattr(self.d,'suspension') else None
 def mark(self,s,d,field):
  pol=self.suspension(s,d)
  if pol:
   if len(self.d.z(s,d)):raise Blocked(f'{day(d)} {s} SUSPENSION_UNEXPECTED_ROW')
   return dec(pol['raw_mark'])
  z=self.d.z(s,d)
  if not finite(z.get(field)) or z[field]<=0:raise Blocked(f"{day(d)} {s} {field.upper()}_MISSING")
  return dec(z[field])
 def qvalue(self,a,d,field):return self.quantity(a)*self.mark(a['sid'],d,field)
 def suspension_event(self,a,d,phase,event,**kw):
  self.suspension_log.append(dict(day=day(d),sid=a['sid'],round_id=a.get('id'),phase=phase,event=event,qty=self.quantity(a),**kw))
 def liquidation_value(self,d,exclude_nontradable=False):
  if not exclude_nontradable and any(self.suspension(s,d) for s in self.active):return None
  return self.cash+self.receivable+sum((self.quantity(a)*self.mark(s,d,'raw_close')*(1-SLIP)-self.d.fee(s,d,self.quantity(a),self.mark(s,d,'raw_close')*(1-SLIP),'sell') for s,a in self.active.items() if not self.suspension(s,d)),ZERO)
 def suspension_preflight(self,s,d,pending,pol):
  a=self.active.get(s);targets=([a] if a else [])+[r for r in pending if r['sid']==s]
  if len(self.d.z(s,d)):raise Blocked(f'{day(d)} {s} SUSPENSION_UNEXPECTED_ROW')
  if self.d.action(s,d) or self.d.events.get((s,d)):raise Blocked(f'{day(d)} {s} SUSPENSION_EQUITY_REQUIRES_SEPARATE_BRIDGE')
  for target in targets:
   if tuple(target['origin'])!=tuple(pol['origin']):raise Blocked(f'{day(d)} {s} SUSPENSION_ANCHOR_SOURCE_MISMATCH')
   if abs(dec(target['factor'])/dec(pol['factor'])-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} SUSPENSION_ANCHOR_FACTOR_MISMATCH')
  self.preflight_log.append(dict(day=day(d),sid=s,status='OFFICIAL_SUSPENSION_ANCHOR_ONLY',held_qty=self.quantity(a) if a else 0,pending_count=sum(r['sid']==s for r in pending),effective_actions=0,observed_source=False,observed_factor=False,origin_matches_anchor=True,factor_matches_anchor=True,mark_source_day=pol['mark_source_day'],raw_mark=pol['raw_mark'],tradable=False))
''' + s[b:]
s=s.replace("  s=a['sid'];p=dec(self.d.z(s,d)[field])*(1-SLIP);q=self.quantity(a)","  s=a['sid']\n  if self.suspension(s,d):raise Blocked(f'{day(d)} {s} NONTRADABLE_NET_NOT_DEFINED')\n  p=dec(self.d.z(s,d)[field])*(1-SLIP);q=self.quantity(a)")
s=s.replace("  for s in sorted(targets):\n   z=self.d.z(s,d)","  for s in sorted(targets):\n   pol=self.suspension(s,d)\n   if pol:\n    self.suspension_preflight(s,d,pending,pol);continue\n   z=self.d.z(s,d)")
needle="    self.equity.append(dict(day=day(d),sid=s,event='FACTOR_BRIDGE',record_qty=self.snapshots.get((s,ev['record_date']),{'q':0})['q'],cash_delta='0',receivable_delta='0',event_id=ev.get('economic_event_id_candidate',f'{s}|{day(d)}')))"
s=s.replace(needle,needle+"\n   if day(d)>='2024-10-28':self.preflight_log.append(dict(day=day(d),sid=s,status='ORIGINAL_OBSERVED_SOURCE_CHECKS_PASS',held_qty=self.quantity(a) if a else 0,pending_count=sum(r['sid']==s for r in pending),effective_actions=len(act),admitted_event=ev is not None,observed_source=True,observed_factor=True,tradable=True))")
s=s.replace("  for s,a in sorted(list(self.active.items())):\n   z=self.d.z(s,d)","  for s,a in sorted(list(self.active.items())):\n   if self.suspension(s,d):\n    self.suspension_event(a,d,'OPEN','EXIT_DEFERRED_NONTRADABLE' if a['exit'] or any(l.get('exit') for l in a['lots']) else 'NO_TRADE_SUSPENSION',locked_exit=a['exit'],locked_lot_exits=[l['id'] for l in a['lots'] if l.get('exit')]);continue\n   z=self.d.z(s,d)")
needle="   s=r['sid'];a=self.active.get(s);z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None"
repl="""   s=r['sid'];a=self.active.get(s)
   if self.suspension(s,d):
    self.candidates.append(dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],decision='SUSPENDED_NONTRADABLE',allocation_rank=rank+1,cp_id=r.get('cp_id'),close_net=r.get('close_net'),open_net=None,planned_q=r['planned_q'],executed_q=0,attempt_budget=str(r['budget']),stock_cap=str(max(ZERO,D('.10')*pre_nav-sv.get(s,ZERO))),sector_cap=str(max(ZERO,D('.10')*pre_nav-sec[self.d.sid_sector[s]])),cash_reserve=str(max(ZERO,cash-D('.10')*pre_nav))));continue
   z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None"""
assert needle in s;s=s.replace(needle,repl)
needle="   if not valid(z) or not finite(z.get('raw_close')) or z['raw_close']<=0 or lineage(z)!=a['origin']:raise Blocked(f'{day(d)} {s} CLOSE_INVALID')"
repl="""   if self.suspension(s,d):
    if self.d.stock.at[d,s]!=-1:raise Blocked(f'{day(d)} {s} SUSPENDED_STOCK_STATE_NOT_UNKNOWN')
    if a['add_count']==0 and sec.state==0:a['exit']=a['exit'] or 'TRIAL_SECTOR_FALSE'
    self.candidates.append(dict(day=day(d),phase='CLOSE',sid=s,round_id=a['id'],event='ADD_GATE',decision='SUSPENDED_NO_PRICE_SIGNAL',sector_state=int(sec.state),sector_strength=bool(sec.strength),cp_id=a['cp']['id'] if a.get('cp') else None,close_net=None,add_count=a['add_count']))
    self.suspension_event(a,d,'CLOSE','STALE_MARK_ONLY_NO_PRICE_SIGNAL',raw_mark=str(self.mark(s,d,'raw_close')),mark_source_day=self.suspension(s,d)['mark_source_day'],locked_exit=a['exit'],stock_state='UNKNOWN');continue
"""+needle
assert needle in s;s=s.replace(needle,repl)
oldliq="str(self.cash+self.receivable+sum((self.quantity(a)*dec(self.d.z(s,d)['raw_close'])*(1-SLIP)-self.d.fee(s,d,self.quantity(a),dec(self.d.z(s,d)['raw_close'])*(1-SLIP),'sell') for s,a in self.active.items()),ZERO))"
assert oldliq in s;s=s.replace(oldliq,"str(self.liquidation_value(d)) if self.liquidation_value(d) is not None else None")
needle="  for s,a in self.active.items():\n   for l in a['lots']:self.holdings.append"
s=s.replace(needle,"""  stale=sum((self.qvalue(a,d,'raw_close') for s,a in self.active.items() if self.suspension(s,d)),ZERO)
  if stale:self.ledger[-1].update(valuation_basis='MARKED_NAV_INCLUDES_NONTRADABLE_STALE_ASSET',stale_market_value=str(stale),nontradable_stocks=sum(bool(self.suspension(s,d)) for s in self.active),tradable_subset_net_liquidation_value=str(self.liquidation_value(d,True)),whole_account_liquidation_available=False)
  for s,a in self.active.items():
   for l in a['lots']:self.holdings.append""")
s=s.replace("raw_mark=str(self.d.z(s,d)['raw_close']),market_value=str(l['q']*dec(self.d.z(s,d)['raw_close']))","raw_mark=str(self.d.z(s,d)['raw_close']) if not self.suspension(s,d) else str(self.mark(s,d,'raw_close')),market_value=str(l['q']*self.mark(s,d,'raw_close'))")
s=s.replace("locked_exit=a['exit'] or l.get('exit')))\n  self.attribute", "locked_exit=a['exit'] or l.get('exit'),**(dict(stale=True,tradable=False,observed_bar=False,mark_source_day=self.suspension(s,d)['mark_source_day'],valuation_only=True) if self.suspension(s,d) else {})))\n  self.attribute")
s=s.replace(' def run(self,checkpoint=False):',' def run(self,checkpoint=False,prefix_only=False):')
s=s.replace("'equity','sector_daily'];lengths", "'equity','sector_daily','suspension_log','preflight_log'];lengths")
a=s.index("    if checkpoint and day(d)=='",s.index('def run(self'));b=s.index("    if checkpoint and day(d)=='2024-09-23':",a)
s=s[:a]+'''    if checkpoint and day(d)=='2024-10-25':
     self.pending=pending;replay=O/('replay_20241025' if prefix_only else 'full_replay_20241025');self.export(replay);checks={}
     prior=O.parent/'joint51_candidate_v9_facts/full_20241031_once'
     for name in ['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END']:
      oldp=prior/(name+'.json');newp=replay/(name+'.json');assert read(oldp)==read(newp) and oldp.read_bytes()==newp.read_bytes(),('PRIOR_PREFIX_MISMATCH',name);checks[name]=len(read(newp))
     qa=dict(result='PASS',certified_through='2024-10-25',economic_alpha_rule_changes=0,exact_records=checks,byte_exact=True)
     save(O/('PRIOR_PREFIX_REPLAY_QA.json' if prefix_only else 'FULL_RUN_PRIOR_PREFIX_REPLAY_QA.json'),qa);print('PRIOR_PREFIX_REPLAY_PASS '+json.dumps(checks),flush=True)
     if prefix_only:break
''' + s[b:]
s=s.replace("if checkpoint and day(d)=='2024-09-23':","if checkpoint and not prefix_only and day(d)=='2024-09-23':")
s=s.replace("  save(path/'ATTEMPTS.json',archive);", "  save(path/'SUSPENSION_EVENTS.json',self.suspension_log);save(path/'PREFLIGHT_CHECKS.json',self.preflight_log)\n  save(path/'ATTEMPTS.json',archive);")
s=s.replace("choices=['synthetic','freeze','run']", "choices=['synthetic','freeze','replay','run']")
s=s.replace("v['checks']+=joint_tests();save", "v['checks']+=joint_tests();from synthetic_suspension import run as suspension_tests;v['checks']+=suspension_tests();save")
s=s.replace("e=Engine(d).run(checkpoint=True);e.export(O/args.output);print", "\n  if args.mode=='run':assert read(O/'PRIOR_PREFIX_REPLAY_QA.json')['result']=='PASS'\n  e=Engine(d).run(checkpoint=True,prefix_only=args.mode=='replay')\n  if args.mode=='run':e.export(O/args.output)\n  print")
s=s.replace(" def order(self,a,d,side,q,p,reason,**kw):\n"," def order(self,a,d,side,q,p,reason,**kw):\n  if self.suspension(a['sid'],d):raise Blocked(f\"{day(d)} {a['sid']} SUSPENDED_ORDER_FORBIDDEN\")\n")
compile(s,str(N/'engine.py'),'exec');(N/'engine.py').write_text(s)
print('ENGINE_WRITTEN',hashlib.sha256((N/'engine.py').read_bytes()).hexdigest())
