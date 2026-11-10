"""The frozen seven levels plus a finite causal participation projection."""
import math
import numpy as np,pandas as pd
from common import TEMP_POLICIES

def trigger(previous,current,kind):
 if previous<1 or current<1:return False
 if kind=='E34':return previous==3 and current==4
 if kind=='E45':return previous==4 and current==5
 if kind=='C4':return previous<4 and current>=4
 if kind=='C5':return previous<5 and current>=5
 raise ValueError(kind)

def project(raw,entry,exit):
 assert entry in ['E34','E45','C4','C5'] and exit in ['S','X6','X7']
 threshold=None if exit=='S' else int(exit[-1]);active=False;armed=False;floor=math.nan;sid=None;prior=0;rows=[]
 for dt,r in raw.iterrows():
  grade=int(r.level)+1 if r.ready and r.level>=0 else 0
  structural=bool(r.ready and r.structure and np.isfinite(r.floor));gid=r.structure_id if structural else None
  ent=ex=0;kind=reason='';floor_for_row=floor
  if active:
   if (not structural or bool(r.structural_invalidated) or gid!=sid):reason='temperature_structure_invalid'
   else:
    floor=max(floor,float(r.floor));floor_for_row=floor
    if threshold is not None and grade>=threshold:armed=True
    if threshold is not None and armed and grade<threshold:reason='cool_below_'+str(threshold)
   if reason:active=False;ex=1;armed=False
  event=bool(structural and not r.structural_invalidated and trigger(prior,grade,entry) and not ex)
  if event and not active:
   active=True;ent=1;sid=gid;floor=float(r.floor);floor_for_row=floor;armed=bool(threshold is not None and grade>=threshold);kind=entry
  # Event remains available if a prior buy was cancelled, but is never invented
  # simply because this market participation state remains active.
  rows.append(dict(date=dt,target=int(active),entered=ent,exited=ex,buy_event=int(event),floor=floor_for_row if active or ex else math.nan,exit_line=floor_for_row if active or ex else math.nan,entry_kind=kind,exit_reason=reason,grade=grade,exit_armed=int(armed),structure_id=gid))
  prior=grade
 return pd.DataFrame(rows).set_index('date')

def original(raw):
 s=raw.copy();s['exit_line']=s.floor;s['entry_kind']=np.where(s.entered,'original_temperature_reach5','');s['exit_reason']=np.where(s.exited,'original_temperature_structure','');s['grade']=np.where(s.ready,s.level+1,0);return s

def layer3(raw):
 s=raw.copy();s['exit_line']=s.floor;s['exit_reason']=s.exit_kind;return s

def initial(d,s,start):
 first=d.index.get_loc(d.loc[start:].index[0]);assert first>0;p=s.iloc[first-1]
 return dict(active=bool(p.target),floor=float(p.floor) if p.target else None,previous_close=float(d.close.iloc[first-1]))
