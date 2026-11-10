
from pathlib import Path
import ast,json,math,hashlib
import pandas as pd,numpy as np
root=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
d=root/'selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/cp_band_structure_case_audit_v1'
source=d/'audit_fixed_cases.py'
tree=ast.parse(source.read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='calculate')
code=ast.get_source_segment(source.read_text(),node)
ns={'pd':pd,'np':np,'math':math}
exec(compile(code,str(source),'exec'),ns)
oldcalc=ns['calculate']
new=code.replace("last_expand=None;last_breach=None\n for day","last_expand=None;last_breach=None;marker=math.nan;marker_day=None\n for day")
new=new.replace("state_before=state;Sbefore=S;Sday_before=Sday","""if 'source_reset' in event or not bool(fr.i_target):marker=math.nan;marker_day=None
  state_before=state;Sbefore=S;Sday_before=Sday""")
new=new.replace("expanding_now=bool(receipt and math.isfinite(up)and fr.close>up)","""if state=='REPAIR':
   if math.isfinite(marker) and fr.close<=marker:marker=math.nan;marker_day=None
   if bool(fr.i_target) and not math.isfinite(marker) and math.isfinite(up) and fr.close>up:
    marker=up;marker_day=str(day.date())
  else:marker=math.nan;marker_day=None
  marker_at_assessment=marker;marker_day_at_assessment=marker_day
  price_armed=bool(state=='REPAIR' and bool(fr.i_target) and math.isfinite(marker) and fr.close>marker)
  expanding_now=bool(receipt and math.isfinite(up) and (fr.close>up or price_armed))""")
new=new.replace("q=q,state_before=","marker=marker_at_assessment,marker_day=marker_day_at_assessment,price_armed=price_armed,q=q,state_before=")
exec(compile(new,'two_clock_candidate_in_memory','exec'),ns)
newcalc=ns['calculate']

idx=pd.bdate_range('2020-01-01',periods=29)
prices=[100.]*21+[110.,105.,120.,121.,121.,121.,121.,122.]
f=pd.DataFrame(dict(close=prices,raw_close=prices,factor=1.,segment_id=1,i_target=True,i_buy=True,g_grade=3),index=idx)
cp=pd.DataFrame(dict(delta_frontier=0.,m=1.,credit=10.,receipt=False,candidate=np.nan,reset_reason='',phase='UP',r=0.),index=idx)
for j,F in [(21,109.),(28,110.)]:
 cp.iloc[j,cp.columns.get_loc('receipt')]=True
 cp.iloc[j,cp.columns.get_loc('candidate')]=F
 cp.iloc[j,cp.columns.get_loc('delta_frontier')]=.1
 cp.iloc[j,cp.columns.get_loc('reset_reason')]='receipt_consumed'
a=oldcalc(f,cp);b=newcalc(f,cp)
print(pd.DataFrame(dict(C=f.close,U=a.upper_prior,CP=cp.receipt,old_state=a.state_after,new_state=b.state_after,old_mult=a.multiplier,new_mult=b.multiplier,marker=b.marker,marker_day=b.marker_day)).tail(8).to_string())
assert a.multiplier.iloc[-1]<1 and b.multiplier.iloc[-1]==1
print('NONEMPTY_MECHANISM_SYNTHETIC_WITNESS_PASS')
