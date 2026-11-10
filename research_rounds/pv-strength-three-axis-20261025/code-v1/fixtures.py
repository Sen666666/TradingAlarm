"""Finite synthetic suite selected before formal B2 output."""
import numpy as np,pandas as pd
from common import OLD
LEGACY=['fast_start','slow_rise','consolidation','bear_rebound','true_weakening','lowvol_selloff',
        'one_pulse','same_end_recovery','same_end_retracement']
def make(logreturns,volumes=None):
    r=np.asarray(logreturns,float);v=np.full(len(r),100.) if volumes is None else np.asarray(volumes,float)
    return pd.DataFrame(dict(close=100*np.exp(np.cumsum(r)),volume=v,segment_id=0,valid_strength_observation=True),
        index=pd.bdate_range('2018-01-01',periods=len(r),name='date'))
def fixtures():
    out={k:pd.read_parquet(OLD/'validation'/(k+'.parquet'))[['close','volume','segment_id','valid_strength_observation','strength']].rename(columns={'strength':'b1_strength'}) for k in LEGACY}
    for key in ['fast_start','lowvol_selloff']:
        f=out[key].drop(columns='b1_strength').copy();f['close']=float(f.close.iloc[0])**2/f.close
        out['mirror_'+key]=f
    rng=np.random.default_rng(20261025);warm=rng.normal(0,.003,120)
    shared=np.r_[warm,np.full(60,-.004),np.full(10,.008)]
    for key,tail in [('V_continues',np.full(50,.006)),('rebound_fails',np.full(50,-.006))]:
        r=np.r_[shared,tail];v=np.full(len(r),100.);v[180]=400.;v[190]=400.
        out[key]=make(r,v)
    rise=np.r_[warm,np.full(70,.003)]
    level=.008*np.sin(2*np.pi*np.arange(1,161)/10)
    out['flat_box']=make(np.r_[rise,np.diff(np.r_[0.,level])])
    out['constant']=make(np.zeros(180))
    r=np.r_[rise,-.12,np.zeros(30)];v=np.full(len(r),100.);v[len(rise)]=1.
    out['single_lowvol_shock']=make(r,v)
    r=np.r_[warm,[-.08,.03,-.04,.05,-.05,.20,0.,-.03,.01,.02],np.zeros(20)]
    v=np.full(len(r),100.);v[120]=400.;v[127]=400.
    out['debt_partial_revisit']=make(r,v)
    assert len(out)==17
    return out
