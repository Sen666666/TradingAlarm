"""B5-G1: ordinal, non-compensating evidence levels with causal promotion receipts."""
import math
import numpy as np
import pandas as pd

LABELS={-3:'强冷',-2:'冷',-1:'弱冷',0:'未立/中性',1:'修复',2:'暖',3:'热',4:'扩张'}
COLORS={-3:'#425479',-2:'#648abd',-1:'#9cb9d4',0:'#c6cbd0',1:'#eadca6',2:'#efb97c',3:'#e88763',4:'#bd3d48'}

def classify(e):
    required=['segment_id','valid_strength_observation','close','event','strength_mu5','strength_mu21','strength_s','strength_S21','strength_S63','strength_r','strength_qeff','strength_acute_down','strength_acute_up','strength_confirmed_direction_21','strength_confirmed_direction_63','strength_running_extreme_price_21']
    if any(c not in e for c in required):raise ValueError('Missing G1 evidence')
    if not e.index.is_unique or not e.index.is_monotonic_increasing:raise ValueError('Ordered unique observations required')
    rows=[];events=[];previous_segment=None;previous_grade=None;prior_extreme=math.nan;prior_s21=0
    for dt,r in e.iterrows():
        segment=str(r.segment_id)
        if segment!=previous_segment:
            previous_grade=None;prior_extreme=math.nan;prior_s21=0;previous_segment=segment
        out=dict(date=dt,segment_id=segment,ready=False,proposal=np.nan,grade=np.nan,score=np.nan,label='未知',phase='unknown',z5=np.nan,z21=np.nan,fresh_up=False,up_reasons='',transition='unknown',promotion_blocked=False,acute_down=False,acute_up=False,display='未知')
        if not bool(r.valid_strength_observation) or not np.isfinite(r.strength_mu21):rows.append(out);continue
        a,b=int(r.strength_S21),int(r.strength_S63);m5=float(r.strength_mu5);m21=float(r.strength_mu21);scale=float(r.strength_s)
        z5=math.sqrt(5)*m5/scale;z21=math.sqrt(21)*m21/scale
        down=bool(r.strength_acute_down);up=bool(r.strength_acute_up)
        reasons=[]
        if int(r.event)==1:reasons.append('new_E0_price_volume_up_event')
        for h in [21,63]:
            if float(r[f'strength_confirmed_direction_{h}'])==1:reasons.append(f'new_S{h}_up_confirmation')
        ext=float(r.strength_running_extreme_price_21)
        if a==1 and prior_s21==1 and np.isfinite(prior_extreme) and ext>prior_extreme+32*np.finfo(float).eps*max(abs(ext),abs(prior_extreme),1):reasons.append('new_price_frontier_in_confirmed_up_structure')
        fresh=bool(reasons)
        if a==0 and b==0:g=0;why='structure_unconfirmed'
        elif m21<0 and m5<=0:g=-3 if a==b==-1 else -2;why='both_paces_negative'
        elif m21<0 and m5>0:g=1 if a==1 else -1;why='local_repair' if a==1 else 'countertrend_rebound'
        elif m21>0:
            if a==b==1:g=3;why='up_structure_and_positive_medium_pace'
            elif a==1:g=2;why='local_up_with_positive_medium_pace'
            elif m5>0:g=1;why='pace_recovery_not_locally_confirmed'
            else:g=-1;why='local_support_missing'
        else:g=1 if m5>0 else -1 if m5<0 else 0;why='medium_pace_zero'
        if a==b==1 and z5>=1 and z21>=1:g=4;why='two_scale_pace_expansion'
        launch=up and int(r.event)==1 and m5>0
        if launch and g<2:g=2;why='acute_up_and_new_volume_price_up_event'
        if z5<=-1 and g>-2:g=-2;why='fast_adverse_displacement'
        if down:g=min(g,-3);why='acute_down_overrides_old_structure'
        proposal=g;old=previous_grade
        blocked=old is not None and proposal>old and not fresh
        if blocked:g=old
        transition='initialize' if old is None else 'upgrade' if g>old else 'downgrade' if g<old else 'blocked_upgrade' if blocked else 'unchanged'
        if down:phase='acute_down'
        elif launch:phase='fast_launch'
        elif up:phase='acute_up'
        elif a==b==1 and z5>=1 and z21>=1:phase='expansion'
        elif m21<0 and m5>0:phase='local_repair' if a==1 else 'downtrend_rebound'
        elif m21<0 and m5<=0:phase='decline'
        elif a==b==1 and (m5<0 or abs(z21)<1):phase='up_structure_consolidation'
        elif a==b==1:phase='up_continuation'
        elif a==1:phase='up_structure_building'
        elif a==b==0:phase='unconfirmed'
        else:phase='mixed_evidence'
        out.update(ready=True,proposal=proposal,grade=g,score=25*g,label=LABELS[g],phase=phase,z5=z5,z21=z21,fresh_up=fresh,up_reasons='|'.join(reasons),transition=transition,promotion_blocked=blocked,acute_down=down,acute_up=up,display=('freeze·' if down else '')+LABELS[g],reason=why)
        if transition!='unchanged':events.append(dict(date=str(dt.date()),segment=segment,previous=old,proposal=proposal,grade=g,score=25*g,kind=transition,basis=why,new_up_evidence=reasons))
        rows.append(out);previous_grade=g;prior_extreme=ext;prior_s21=a
    f=pd.DataFrame(rows).set_index('date')
    return f,events
