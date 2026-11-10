from pathlib import Path
import json
import numpy as np,pandas as pd
from clock_model import relative_clock,cached_receipts,obs,delta
O=Path(__file__).resolve().parent
g=np.r_[np.ones(80),.9875468618243614,np.ones(10),.9875468618243614,np.ones(10),.9875468618243614,np.ones(10)]
v=np.r_[False,np.ones(len(g)-1,bool)]
z=relative_clock(100*g,1000*g,v);assert not z.relative_event.ne(0).any()
x=np.r_[np.cumsum(np.tile([.01,-.01],40)),np.linspace(0,.10,25),np.linspace(.10,-.05,35),np.linspace(-.05,.08,30)]
c=100*np.exp(x);s=np.full(len(x),1000.);v=np.r_[False,np.ones(len(x)-1,bool)]
a=relative_clock(c,s,v);b=relative_clock(c*2**10,s*2**10,v)
pd.testing.assert_frame_equal(a,b)
inverse=relative_clock(s,c,v);assert (a.relative_event.to_numpy()==-inverse.relative_event.to_numpy()).all()
for n in [90,115,150]:pd.testing.assert_frame_equal(relative_clock(c[:n],s[:n],v[:n]),a.iloc[:n].reset_index(drop=True))
assert delta(obs(100,1000,3),obs(100,1000,3))==(0,0)
days=pd.bdate_range('2022-01-03',periods=6)
def frame():
 return pd.DataFrame(dict(relative_known=True,relative_event=[1,0,0,0,0,0],M3_known=True,M3=[False,False,True,True,True,True],mu5=.01,sectorS=1,I_qualified=True,I_continuity_epoch=1),index=days)
out=[]
f=frame();e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert e.day.tolist()==[days[2]] and e.delay.tolist()==[2];out.append('l1 completes atage2 beforeexpiry')
f=frame();f.relative_event=[0,1,0,0,0,0];e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert e.day.tolist()==[days[2]] and e.delay.tolist()==[1];out.append('l2 completes atage1')
for column,value in [('mu5',0),('sectorS',-1),('I_qualified',False),('M3_known',False),('relative_known',False),('relative_event',-1),('I_continuity_epoch',2)]:
 f=frame();f.loc[days[1],column]=value;e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert len(e)==0,(column,e);out.append('cancel '+column)
for posday in [days[0],days[1],days[2]]:
 f=frame();e,t=cached_receipts(f,days[0],days[-1],calendar=days,position={d:('HELD' if d==posday else 'FLAT') for d in days});assert len(e)==0;out.append('held blocks/cancels '+str(posday.date()))
f=frame();f.M3=True;e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert e.day.tolist()==[days[0]] and len(e)==1;out.append('immediate no replay')
f=frame();e,t=cached_receipts(f,days[0],days[-1],calendar=days,arm='SAME_DAY');assert len(e)==0;out.append('same-day baseline misses unready')
f=frame();f.M3=False;e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert len(e)==0 and t.action.eq('EXPIRED_CONSISTENCY_FAILURE').sum()==1;out.append('inconsistentdeadline noextension')
f=frame();e,t=cached_receipts(f,days[0],days[-1],calendar=days,position={days[0]:'FLAT'});assert len(e)==0;out.append('explicit missing position is UNKNOWN')
f=frame();f.loc[days[0],'M3']=np.nan;e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert len(e)==0;out.append('knownflag withNaNM3 doesnotarm')
maxp=np.finfo(float).max;zz=relative_clock(np.full(80,maxp),np.full(80,1000.),np.r_[False,np.ones(79,bool)]);assert zz.relative_reason.eq('INVALID_OR_UNBOUNDED_PRICE').all()
f=frame();f.relative_event=[0,0,1,0,0,0];f.M3_known=[False,False,True,True,True,True];f.M3=[False,False,False,True,True,True];f.mu5=[-.01,.01,.01,.01,.01,.01];e,t=cached_receipts(f,days[0],days[-1],calendar=days);assert e.arm_streak.tolist()==[2] and e.delay.tolist()==[1] and t.loc[2,'deadline']==days[3];out.append('mu streak distinct fromM3known warmup')
(O/'SYNTHETIC_TESTS.json').write_text(json.dumps(dict(constant_commonfactor_false_events=0,price_power2_scale_invariant=True,inverse_direction_symmetric=True,prefixes=3,same_observation_delta_exactzero=True,cache_tests=out,count=len(out)),indent=2)+'\n')
print('PASS numeric and',len(out),'cache tests;events',a.relative_event.value_counts().to_dict())
