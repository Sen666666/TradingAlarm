def advance(w,*,day,j,L,close,old_floor,event,pivot,pivot_date,valid,segment,on):
 w=dict(w)
 reason='risk_pause' if not on else 'structure_or_source' if not valid or segment!=w['segment'] else 'expired' if j-w['j']>=L else 'waiting_floor_breach' if close<=w['floor'] else None
 if reason:return None,reason
 floor=max(w['floor'],old_floor)
 if event==1 and pivot_date>=w['day']:floor=max(floor,pivot)
 if close<=floor:return None,'updated_floor_breach'
 w['floor']=floor
 return w,None
