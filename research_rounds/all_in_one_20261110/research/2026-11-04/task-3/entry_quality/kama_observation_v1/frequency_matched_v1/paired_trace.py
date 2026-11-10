"""Two fixed closing-protection shadows, common market labels; no account."""
import math
import numpy as np
from core import ge

def positive(x):
    return x is not None and np.isfinite(x) and x>0

def run(pair,a,price):
    """Input already passes core.anchor_only; EMA matrix has exactly locked N.

    Market-label horizon is native I/source, not either rule's exit. Only old P
    tests today's C; today's new proposal is effective at the next close.
    """
    assert a['EMA'].shape[1]==1 and len(price)==len(a['C'])
    anchor=a['lookup'][pair['anchor_day']]
    entry=a['lookup'][pair['entry_reference']['next_observation_day']]
    E=float(pair['entry_reference']['OPEN']);P0=float(pair['P0']);source=a['source'][anchor]
    n=len(price);O=price.open.to_numpy(float)
    rawO=price.raw_open.to_numpy(float) if 'raw_open' in price else np.full(n,np.nan)
    assert positive(E) and positive(P0) and E>P0 and math.isclose(E,O[entry],rel_tol=1e-12,abs_tol=1e-12)
    def quote(j):
        k=j+1
        if k>=n:return dict(day=None,OPEN=None,raw_OPEN=None,status='NO_NEXT_SOURCE_OBSERVATION')
        if not a['valid'][k] or a['source'][k]!=source or not positive(O[k]):
            return dict(day=a['days'][k],OPEN=None,raw_OPEN=None,status='NEXT_SOURCE_QUOTE_UNKNOWN_OR_INCOMPARABLE')
        return dict(day=a['days'][k],OPEN=float(O[k]),raw_OPEN=float(rawO[k]) if positive(rawO[k]) else None,status='REFERENCE_ONLY_NOT_PROVEN_EXECUTABLE')
    # Common native-I market horizon, independently of either protection exit.
    span=[];common_reason='SOURCE_END';boundary=None
    for j in range(entry,n):
        if a['source'][j]!=source or a['native_source'][j]!=source:
            common_reason='SOURCE_INCOMPARABLE';boundary=j;break
        if not a['valid'][j]:common_reason='UNKNOWN_CLOSE';boundary=j;break
        if a['I'][j] is None:common_reason='UNKNOWN_I';boundary=j;break
        if a['I'][j]==1 and not positive(a['IF'][j]):common_reason='UNKNOWN_I_FLOOR';boundary=j;break
        span.append(j)
        if a['I'][j]==0:common_reason='ORIGINAL_I_INVALID';boundary=j;break
    values=a['C'][span]
    common_max=max(E,float(values.max())) if len(values) else None
    common_min=min(E,float(values.min())) if len(values) else None
    P=np.full(2,P0);alive=np.ones(2,dtype=bool);origin=['COMMON_P0','COMMON_P0']
    peak=np.full(2,E);mfe=np.zeros(2);mae=np.zeros(2);dd=np.zeros(2)
    arms=[dict(label='KAMA'),dict(label='EMA')]
    pending_above=np.zeros(2,dtype=int)
    for j in span:
        C=float(a['C'][j]);age=j-entry+1
        for k in range(2):
            if not alive[k]:continue
            peak[k]=max(peak[k],C);mfe[k]=max(mfe[k],C/E-1);mae[k]=max(mae[k],1-C/E);dd[k]=max(dd[k],1-C/peak[k])
        if a['I'][j]==0:
            for k in range(2):
                if alive[k]:arms[k].update(outcome='EXIT_SIGNAL',exit_day=a['days'][j],exit_age=age,exit_index=j,exit_reason='ORIGINAL_I_INVALID',exit_line=float(P[k]),exit_line_origin=origin[k],exit_C=C,next_OPEN=quote(j));alive[k]=False
            break
        for k in range(2):
            if alive[k] and bool(ge(P[k],C)):
                arms[k].update(outcome='EXIT_SIGNAL',exit_day=a['days'][j],exit_age=age,exit_index=j,exit_reason='EXIT_STORED_LINE',exit_line=float(P[k]),exit_line_origin=origin[k],exit_C=C,next_OPEN=quote(j));alive[k]=False
        if not alive.any():break
        bands=np.array([a['K'][j],a['EMA'][j,0]])*math.exp(-a['s'][j]) if a['scale'][j]=='READY' and positive(a['s'][j]) else np.full(2,np.nan)
        for k in range(2):
            if not alive[k]:continue
            if not positive(bands[k]):
                arms[k].update(outcome='UNKNOWN',censor_day=a['days'][j],censor_reason='PROTECTION_INPUT_UNKNOWN',observations=age);alive[k]=False;continue
            old=float(P[k]);Q=max(old,float(a['IF'][j]),float(bands[k]))
            if Q>old:
                origin[k]='INDICATOR_BAND' if bands[k]>max(old,a['IF'][j]) else 'I_FLOOR'
            assert Q>=old
            if bool(ge(Q,C)):pending_above[k]+=1
            P[k]=Q
    for k,r in enumerate(arms):
        if alive[k]:r.update(outcome='RIGHT_CENSORED' if common_reason=='SOURCE_END' else 'UNKNOWN',censor_reason=common_reason,censor_day=None if boundary is None else a['days'][boundary],observations=len(span))
        held=r.get('exit_age',r.get('observations',len(span)))
        r.update(observations=held,MFE_while_held=float(mfe[k]) if held else None,MAE_while_held=float(mae[k]) if held else None,max_close_drawdown_while_held=float(dd[k]) if held else None,
                 pending_new_line_above_close_steps=int(pending_above[k]))
        j=r.pop('exit_index',None)
        if j is not None:
            Q=r['next_OPEN'].get('OPEN')
            r['exit_OPEN_unit_price_change']=None if not positive(Q) else Q/E-1
            r['giveback_to_exit_OPEN_in_entry_units']=None if not positive(Q) else (peak[k]-Q)/E
            r['common_higher_peak_after_exit_in_entry_units']=max(0.,common_max-peak[k])/E if common_max is not None else None
            later=[z for z in span if z>j]
            r['remaining_I_horizon_max_close_after_exit']=None if not later else float(a['C'][later].max())
            r['remaining_I_horizon_min_close_after_exit']=None if not later else float(a['C'][later].min())
        # A common fixed-age quotation value: exit reference if exited by 20,
        # otherwise next OPEN after the twentieth completed close. Never reenter.
        r['H20_unit_price_change']=None;r['H20_kind']='UNAVAILABLE'
        if r.get('exit_age',21)<=20:
            Q=r.get('next_OPEN',{}).get('OPEN')
            if positive(Q):r['H20_unit_price_change']=Q/E-1;r['H20_kind']='EARLY_EXIT_REFERENCE_HELD_FLAT'
        elif r['outcome']!='UNKNOWN' or r.get('observations',0)>20:
            j20=entry+19
            if j20<n and j20 in span:
                Q=quote(j20).get('OPEN')
                if positive(Q):r['H20_unit_price_change']=Q/E-1;r['H20_kind']='COMMON_20TH_CLOSE_NEXT_OPEN_MARK_NOT_EXIT'
    return dict(E_reference=E,P0=P0,entry_day=a['days'][entry],not_actual_position=True,
        common_market_end_reason=common_reason,common_market_end_day=None if not span else a['days'][span[-1]],common_market_observations=len(span),
        common_MFE=None if common_max is None else common_max/E-1,common_MAE=None if common_min is None else 1-common_min/E,
        common_price_peak=common_max,common_price_min=common_min,common_label_is_observed_lower_bound=common_reason!='ORIGINAL_I_INVALID',
        KAMA=arms[0],EMA=arms[1])
