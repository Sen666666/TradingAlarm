from pathlib import Path
p=Path(__file__).resolve().parent/'engine.py';s=p.read_text()
s=s.replace('class Engine(m7.Engine):', '''SID='605499.SH';EX_DATE='2024-10-09';RECORD_DATE='2024-10-08'

def q0_guard(e,d,pending):
 if day(d)!=EX_DATE:return None
 def require(v,reason):
  if not v:raise Blocked(f'{day(d)} {SID} Q0_SPLIT_SCOPE_{reason}')
 t=e.tickets.get(SID);snap=e.snapshots.get((SID,RECORD_DATE))
 require(t is not None and t.get('ever_seeded') is False and t.get('status') not in ('CANCELLED','CONSUMED'),'LIVE_NEVER_SEEDED_TICKET_REQUIRED')
 require(SID not in e.active,'ACTIVE_POSITION')
 require(not any(a['sid']==SID for a in e.archive.values()),'HISTORICAL_ROUND')
 require(not any(o['sid']==SID for o in e.orders),'HISTORICAL_ORDER')
 require(snap is not None and snap.get('q')==0 and snap.get('round') is None,'EXPLICIT_ZERO_RECORD_SNAPSHOT_REQUIRED')
 require(not any(k[0]==SID for k in e.claims),'EXISTING_ENTITLEMENT')
 require(not any(r['sid']==SID for r in pending) and t.get('plan') is None,'PENDING_REQUEST')
 require(not any(r['sid']==SID for r in e.transfer_plan),'TRANSFER_REQUEST')
 z=e.d.z(SID,d);ev=e.d.events.get((SID,d))
 require(ev is not None and ev.get('q0_never_seeded_only') is True,'REVIEWED_Q0_EVENT_REQUIRED')
 require(tuple(m7.m3.lineage(z))==tuple(t['origin']),'SOURCE_CHANGED')
 require(abs(t['current_factor']/m7.dec(ev['factor_old'])-1)<=m7.D('1e-11'),'OLD_FACTOR')
 require(abs(m7.dec(z['adjustment_factor'])/m7.dec(ev['factor_new'])-1)<=m7.D('1e-11'),'NEW_FACTOR')
 return copy.deepcopy(t)

class Engine(m7.Engine):
 def economic_preflight(self,d,pending):
  before=q0_guard(self,d,pending)
  super().economic_preflight(d,pending)
  if before is not None:
   after=self.tickets[SID]
   if {k:v for k,v in before.items() if k not in ('current_factor','last_verified_day')}!={k:v for k,v in after.items() if k not in ('current_factor','last_verified_day')}:
    raise Blocked(f'{day(d)} {SID} Q0_SPLIT_TICKET_IDENTITY_MUTATED')
   self.equity.append(dict(day=day(d),sid=SID,event='Q0_SPLIT_BRIDGE_VERIFIED_NO_ENTITLEMENT',record_qty=0,ex_preexecution_qty=0,cash_delta='0',receivable_delta='0',share_delta=0,ticket_id=after['ticket_id'],factor_old=str(before['current_factor']),factor_new=str(after['current_factor']),original_NAV=str(after['nav0']),original_I=str(after['original_ifloor'])))
''')
s=s.replace("and n!='export'","and n not in ('export','economic_preflight')")
s=s.replace("suspension_changes_installed=False,history_run=False","suspension_changes_installed=False,q0_guard_only_preflight_override=True,history_run=False")
s=s.replace('data=m7.Data(end=', 'data=Data(end=')
p.write_text(s)
