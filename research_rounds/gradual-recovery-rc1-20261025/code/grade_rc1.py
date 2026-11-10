"""Explicit ordinal consumer of original G1 proposals + RC1 receipts."""
import numpy as np
LABELS={-3:'强冷',-2:'冷',-1:'弱冷',0:'未立/中性',1:'修复',2:'暖',3:'热',4:'扩张'}

def classify_with_recovery(e,old,rc,enabled=True):
 out=old.copy();previous=None;segment=None
 fields={'rc_fresh':False,'rc_cap':np.nan,'rc_promoted':False,'rc_promoted_to_warm':False,'rc_only_fresh':False}
 for k,v in fields.items():out[k]=v
 for dt,r in e.iterrows():
  if r.segment_id!=segment:segment=r.segment_id;previous=None
  o=old.loc[dt];c=rc.loc[dt]
  if not bool(o.ready):continue
  proposal=int(o.proposal);original_fresh=bool(o.fresh_up)
  cap=1 if c.context=='down' else 3 if c.context=='up' and c.tier==21 else 2
  new=bool(enabled and c.ready and c.receipt)
  level=proposal;used=False;blocked=False
  if previous is not None and proposal>previous and not original_fresh:
   candidate=min(proposal,cap) if new else previous
   if candidate>previous:level=candidate;used=True
   else:level=previous;blocked=True
  transition='initialize' if previous is None else 'upgrade' if level>previous else 'downgrade' if level<previous else 'blocked_upgrade' if blocked else 'unchanged'
  # RC1 can count as new warm evidence only under its explicit context/tier
  # cap and current proposal. It never bypasses a cold proposal or acute risk.
  usable=new and cap>=2 and proposal>=2 and level>=2
  fresh=original_fresh or used or usable
  out.loc[dt,['grade','score','fresh_up','promotion_blocked','transition']]=[level,25*level,fresh,blocked,transition]
  out.loc[dt,['label','display']]=[LABELS[level],('freeze·' if bool(o.acute_down) else '')+LABELS[level]]
  out.loc[dt,['rc_fresh','rc_cap','rc_promoted','rc_promoted_to_warm','rc_only_fresh']]=[new,cap,used,used and level>=2,usable and not original_fresh]
  if used:out.loc[dt,'up_reasons']=str(o.up_reasons)+('|RC1_new_local_price_volume_progress')
  previous=level
 return out
