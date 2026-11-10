"""Fixed B3 synthetic inputs. No model execution or parameter search here."""
import numpy as np
import pandas as pd
from common import B2, sha

INPUT_COLUMNS=['close','volume','segment_id','valid_strength_observation']
LEGACY=['fast_start','slow_rise','consolidation','bear_rebound','true_weakening',
        'lowvol_selloff','one_pulse','same_end_recovery','same_end_retracement',
        'mirror_fast_start','mirror_lowvol_selloff','V_continues','rebound_fails',
        'flat_box','constant','single_lowvol_shock','debt_partial_revisit']
NEW=['micro_box','micro_rise','ordinary_rise','rise_then_static','slow_decline',
     'shock_then_static','shock_then_recovery']

def make(logreturns,volumes=None):
    r=np.asarray(logreturns,dtype=float)
    v=np.full(len(r),100.,dtype=float) if volumes is None else np.asarray(volumes,dtype=float)
    if r.ndim!=1 or v.shape!=r.shape:raise ValueError('One-dimensional matching returns and volumes required')
    return pd.DataFrame(dict(close=100.*np.exp(np.cumsum(r)),volume=v,
        segment_id=np.zeros(len(r),dtype=int),valid_strength_observation=np.ones(len(r),dtype=bool)),
        index=pd.bdate_range('2018-01-01',periods=len(r),name='date'))

def new_fixtures():
    warm=np.tile([.002,-.002],60);rise=np.full(70,.003)
    level=.00001*np.sin(2*np.pi*np.arange(1,161)/10)
    ordinary=np.r_[warm,np.full(120,.001)]
    crash_static=np.r_[warm,rise,-.12,np.zeros(120)]
    crash_recovery=np.r_[warm,rise,-.12,np.full(4,.03),np.zeros(116)]
    volume=np.full(len(crash_static),100.);volume[190]=1.
    return dict(micro_box=make(np.r_[warm,np.diff(np.r_[0.,level])]),
        micro_rise=make(.01*ordinary),ordinary_rise=make(ordinary),
        rise_then_static=make(np.r_[warm,rise,np.zeros(120)]),
        slow_decline=make(np.r_[warm,rise,np.full(120,-.001)]),
        shock_then_static=make(crash_static,volume),
        shock_then_recovery=make(crash_recovery,volume.copy()))

def fixtures():
    out={key:pd.read_parquet(B2/'validation-v1'/(key+'.parquet'))[INPUT_COLUMNS].copy() for key in LEGACY}
    out.update(new_fixtures())
    if list(out)!=LEGACY+NEW or len(out)!=24:raise AssertionError('Fixed 17+7 fixture identity')
    return out

def fixture_manifest():
    return dict(legacy=[dict(path=key,source=str(B2/'validation-v1'/(key+'.parquet')),
        source_sha256=sha(B2/'validation-v1'/(key+'.parquet')),selected_columns=INPUT_COLUMNS) for key in LEGACY],
        new=NEW,warmup_returns=120,ordinary_rise_start=120,rise_end_observation=189,
        decline_or_shock_or_static_start=190,shock_recovery_complete_observation=194,
        new_price_origin=100.,new_volume_default=100.,accounts=0)

def transforms(fs):
    """Exactly 24 unit, 4 reflection, 2 micro-perturbation, and 2 high-volume inputs."""
    for key,f in fs.items():
        g=f.copy();g['close']=g.close*17.;g['volume']=g.volume*10000.
        yield key+'__units',key,'units',g,dict(price_multiple=17.,volume_multiple=10000.)
    for key in ['micro_box','ordinary_rise','slow_decline','shock_then_static']:
        g=fs[key].copy();g['close']=float(g.close.iloc[0])**2/g.close
        yield key+'__reflection',key,'reflection',g,dict(log_reflection_origin=float(fs[key].close.iloc[0]))
    for sign,label in [(1.,'plus'),(-1.,'minus')]:
        g=fs['micro_box'].copy();n=len(g)-120
        g.loc[g.index[120]:,'close']*=np.exp(sign*1e-7*(-1.)**np.arange(n))
        yield 'micro_box__perturb_'+label,'micro_box','perturbation',g,dict(log_noise=sign*1e-7,start=120)
    for key in ['shock_then_static','shock_then_recovery']:
        g=fs[key].copy();g.iloc[190,g.columns.get_loc('volume')]=400.
        yield key+'__high_volume',key,'high_volume',g,dict(observation=190,volume=400.)

def moderate_volume_inputs():
    """Direct mechanism probe, not a 25th base path or a parameter search."""
    low=make(np.r_[np.tile([.002,-.002],60),np.full(70,.003),-.0045])
    high=low.copy();high.iloc[-1,high.columns.get_loc('volume')]=400.
    return low,high
