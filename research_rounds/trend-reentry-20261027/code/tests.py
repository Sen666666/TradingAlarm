from study import *
import study
from model import compute
from types import SimpleNamespace
from dataclasses import dataclass
rng=np.random.default_rng(1729);idx=pd.bdate_range('2020-01-01',periods=1200);c=100*np.exp(np.cumsum(rng.normal(.001,.015,len(idx))))
f=pd.DataFrame({'close':c,'open':c*.998,'high':c*1.003,'low':c*.997,'amount':rng.uniform(.5e8,2e8,len(idx))},index=idx)
g=pd.DataFrame({'segment_id':0,'e0_target':True,'g_ready':True,'g_grade':2,'e0_floor':c*.7},index=idx);checks=[]
for v in ['PB','BOX','BOTH']:
 z=compute(f,g,v);assert z.event.sum()>0
 pd.testing.assert_frame_equal(compute(f.iloc[:700],g.iloc[:700],v),z.iloc[:700],check_exact=True);checks.append(v+'_prefix')
 for k,q in z[z.event].iterrows():assert 0<f.loc[k,'close']-q.floor<=3*q.atr
 dates=z.index[z.event];anchors=pd.to_datetime(z.loc[dates,'anchor']);assert all(anchors.iloc[i]>dates[i-1] for i in range(1,len(dates)));checks.append(v+'_fresh_structure')
 gg=g.copy();gg.e0_target=False;assert not compute(f,gg,v).event.any();checks.append(v+'_no_down_background')
 ff=f.copy();ff.amount=0;assert not compute(ff,g,v).event.any();checks.append(v+'_amount_required')
 ff=f.copy();ff.amount*=100;pd.testing.assert_frame_equal(compute(ff,g,v),z,check_exact=False,rtol=1e-12);checks.append(v+'_amount_unit_invariance')
 ff=f.copy();ff.loc[idx[600],'amount']=np.nan;assert not compute(ff,g,v).event.loc[idx[600:622]].any();checks.append(v+'_invalid_resets')
# Exercise actual held-position override: no loosening, strict later E0 advance, local exit.
@dataclass
class Stock:
 security_id:str
 trend_up:object
 buy_allowed:object
at=E.datetime(2026,1,6,15,10,tzinfo=E.native.TZ);clock=SimpleNamespace(decision_at=at);stock=Stock('X',E.admission.Fact(True,at,at),E.admission.Fact(True,at,at));events=[]
r=SimpleNamespace(e0_target=True,e0_floor=90.,close=110.)
a=SimpleNamespace(local_positions={'X':dict(stop=D(100),local_floor=D(100),entry_e0_floor=D(90),handed=False)},quantity=lambda sid:100,facts=SimpleNamespace(row=lambda sid,at:r),exits={},log=lambda *args,**kw:events.append((args,kw)))
study.VERSION='PB';study.override(a,(stock,),clock,'CONTROL',E.admission.Fact);assert a.local_positions['X']['stop']==100 and not a.local_positions['X']['handed'];checks.append('no_floor_loosening')
r.e0_floor=101;study.override(a,(stock,),clock,'CONTROL',E.admission.Fact);assert a.local_positions['X']['handed'] and a.local_positions['X']['stop']==101;checks.append('handoff_on_new_support')
r.close=100;r.e0_floor=95;s=study.override(a,(stock,),clock,'CONTROL',E.admission.Fact)[0];assert s.trend_up.value is False and a.local_positions['X']['stop']==101;checks.append('close_stop_after_handoff')
a.quantity=lambda sid:0;study.override(a,(stock,),clock,'CONTROL',E.admission.Fact);assert not a.local_positions;checks.append('flat_clears_local_state')
save(O/'tests.json',{'passed':True,'checks':checks})
print('passed',len(checks))
