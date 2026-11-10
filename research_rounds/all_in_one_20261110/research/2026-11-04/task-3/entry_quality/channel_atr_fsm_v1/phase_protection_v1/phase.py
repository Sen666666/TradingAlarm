"""Fixed EARLY-original-CP -> reached 2S -> TREND4 layer shadow. No accounts."""
import math
import numpy as np

EPS=4*2**-53/(1-4*2**-53)
def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (ValueError,TypeError):return False
def positive(x):return finite(x) and float(x)>0
def flag(x):return bool(x) if isinstance(x,(bool,np.bool_)) else None
def bit(x):return int(x) if finite(x) and float(x) in (0.,1.) else None
def ge(a,b):return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is None:return None
    if isinstance(x,np.generic):x=x.item()
    return None if isinstance(x,float) and not math.isfinite(x) else x
def col(frame,name):return frame[name].to_numpy() if name in frame else np.full(len(frame),None,dtype=object)


def simulate(sid,price,features,native,cp,original_pairs,version):
    """All supplied original anchors retained; original CP branch reused verbatim."""
    n=native.reindex(price.index);c=cp.reindex(price.index)
    days=np.array([str(t.date()) for t in price.index]);where={d:i for i,d in enumerate(days)}
    C=col(price,'close');H=col(price,'high');O=col(price,'open');rawO=col(price,'raw_open')
    cv=col(features,'close_valid');fv=col(features,'valid_bar');seg=col(features,'source_key');atr=col(features,'ATR14_prior')
    I=col(n,'i_target');IF=col(n,'i_floor');receipt=col(c,'receipt');candidate=col(c,'candidate')
    nextobs=np.full(len(days),-1,dtype=np.int64);nxt=-1
    for j in range(len(days)-1,-1,-1):
        nextobs[j]=nxt
        if bool(fv[j]):nxt=j
    def quote(j,line,source):
        q=int(nextobs[j])
        if q<0:return dict(day=None,OPEN=None,raw_OPEN=None,OPEN_minus_exit_line=None,status='NO_NEXT_OBSERVATION')
        if seg[q]!=source or not positive(O[q]):return dict(day=days[q],OPEN=None,raw_OPEN=None,OPEN_minus_exit_line=None,status='UNKNOWN_OR_INCOMPARABLE')
        return dict(day=days[q],OPEN=float(O[q]),raw_OPEN=clean(rawO[q]),OPEN_minus_exit_line=float(O[q])-line,
                    status='REFERENCE_ONLY_NOT_EXECUTABLE_FILL')
    result=[]
    for original in original_pairs:
        a=where.get(original['anchor_day']);base=dict(sid=sid,anchor_day=original['anchor_day'],anchor_id=original.get('anchor_id'),
            version=version,original_pair_status=original['status'],original_CP_control=original.get('CP'),
            original_entry_reference=original.get('entry_reference'),common_end_day=original.get('common_end_day'),
            common_end_reason=original.get('common_end_reason'),execution_unknown=True,actual_layer_migration=False)
        if original['status']!='PAIRED_SHADOWS' or a is None:
            result.append(dict(base,outcome='NOT_EVALUABLE_ORIGINAL_ENTRY_STATE',steps=[]));continue
        entry=original.get('entry_reference') or {};entryday=entry.get('next_observation_day');e=where.get(entryday)
        E=entry.get('OPEN');S=original.get('anchor_ATR_prior');P0=original.get('P0')
        if e is None or not all(positive(x) for x in [E,S,P0]) or ge(float(P0),float(E)):
            result.append(dict(base,outcome='ENTRY_REFERENCE_UNKNOWN_OR_INVALID',steps=[]));continue
        E,S,P=map(float,(E,S,P0));assert float(O[e])==E
        end=where.get(original['common_end_day'],len(days)-1)
        phase='EARLY';MC=MH=E;reached=False;first_reached=None;switched=None;steps=[];ever_unknown=False
        exitday=None;exitreason=None;exitline=None;exitj=None;unknown_reason=None
        for j in range(e,end+1):
            beforeP=P;beforephase=phase;beforeMC=MC;beforeMH=MH
            cknown=bool(cv[j]) and seg[j]==seg[a] and positive(C[j]);value=float(C[j]) if cknown else None
            ri=bit(I[j]);ifknown=positive(IF[j]);rCP=flag(receipt[j]);cpknown=positive(candidate[j])
            step=dict(day=days[j],entry_bar=j==e,phase_before=phase,P_old=P,C=value,I_target=ri,
                I_floor=clean(IF[j]),ATR_prior=clean(atr[j]),M_C_before=MC,M_H_before=MH,
                CP_receipt_state=rCP,CP_candidate=clean(candidate[j]),Q=None,line_driver=None,
                reached_2S_before=reached,phase_switch=False,CP_candidate_adopted=False,
                CP_candidate_not_adopted=None,event=None,unknown_reason=None,
                hypothetical_threshold_true_if_known_C=bool(cknown and ge(max(MC,value)-E,2*S)))
            if not cknown:
                step['event']='UNKNOWN_PENDING';step['unknown_reason']='UNKNOWN_OR_INCOMPARABLE_CLOSE_OR_SOURCE'
            else:
                if ri==0:exitreason='EXIT_ORIGINAL_I_INVALID_CURRENT';exitline=P
                elif ge(P,value):exitreason='EXIT_STORED_LINE';exitline=P
                elif ifknown and ge(float(IF[j]),value):exitreason='EXIT_CURRENT_I_HARD_FLOOR';exitline=float(IF[j])
                if exitreason:
                    step['event']=exitreason
                    step['threshold_preempted_by_existing_exit']=bool(step['hypothetical_threshold_true_if_known_C'] and phase=='EARLY')
                else:
                    MC=max(MC,value)
                    if not reached and ge(MC-E,2*S):reached=True;first_reached=days[j]
                    hard_known=ri==1 and ifknown
                    if not hard_known:
                        step['event']='UNKNOWN_PENDING';step['unknown_reason']='UNKNOWN_CURRENT_I_OR_I_FLOOR'
                    else:
                        if phase=='EARLY' and reached and positive(atr[j]):
                            phase='TREND4';switched=days[j];step['phase_switch']=True
                        if phase=='EARLY':
                            if rCP is None:
                                step['event']='UNKNOWN_PENDING';step['unknown_reason']='UNKNOWN_EARLY_CP_RECEIPT_STATE'
                            elif rCP and not cpknown:
                                step['event']='UNKNOWN_PENDING';step['unknown_reason']='UNKNOWN_EARLY_CP_CANDIDATE'
                            else:
                                Q=max(P,float(IF[j]),float(candidate[j]) if rCP else P)
                                step['Q']=Q;step['CP_candidate_adopted']=bool(rCP)
                                step['line_driver']='CP_CANDIDATE' if rCP and ge(float(candidate[j]),max(P,float(IF[j]))) else 'OLD_P' if ge(P,float(IF[j])) else 'I_HARD_FLOOR'
                        else:
                            if rCP is True:step['CP_candidate_not_adopted']='TREND4_PRECOMMITTED_SKIP_NEW_CP'
                            elif rCP is None:step['CP_candidate_not_adopted']='CP_STATE_UNKNOWN_NOT_REQUIRED_BY_TREND4'
                            if not positive(atr[j]):
                                step['event']='UNKNOWN_PENDING';step['unknown_reason']='UNKNOWN_TREND4_ATR_PRIOR'
                            else:
                                atrline=beforeMH-4.*float(atr[j]);Q=max(P,float(IF[j]),atrline);step['Q']=Q
                                step['line_driver']='OLD_P' if ge(P,max(float(IF[j]),atrline)) else 'I_HARD_FLOOR' if ge(float(IF[j]),atrline) else 'ATR4'
                                step['CP_candidate_would_raise_beyond_Q']=bool(rCP is True and cpknown and not ge(Q,float(candidate[j])))
                        if step['Q'] is not None:
                            if ge(step['Q'],value):
                                exitreason='EXIT_NEW_TREND4_PROPOSAL' if phase=='TREND4' else 'EXIT_NEW_CP_PROPOSAL'
                                exitline=step['Q'];step['event']=exitreason
                            else:P=step['Q'];step['event']='SWITCH_TO_TREND4' if step['phase_switch'] else 'HOLD_EARLY_CP' if phase=='EARLY' else 'HOLD_TREND4'
            if step['unknown_reason']:
                ever_unknown=True;unknown_reason=step['unknown_reason']
            if not exitreason and cknown:
                if j==e:MH=max(MH,value)
                elif bool(fv[j]) and positive(H[j]):MH=max(MH,float(H[j]))
                else:
                    ever_unknown=True;step['peak_H_unknown']=True
            assert P>=beforeP
            step.update(phase_after=phase,P_next=None if exitreason else P,reached_2S_after=reached,
                        pending_2S=bool(reached and phase=='EARLY'),M_C_after=MC,M_H_after=MH,
                        proposed_not_installed=bool(exitreason and step['Q'] is not None))
            steps.append(clean(step))
            if exitreason:exitday=days[j];exitj=j;break
        outcome='EXIT_SIGNAL' if exitday else 'UNKNOWN_PENDING' if ever_unknown or str(original['common_end_reason']).startswith('UNKNOWN') else 'RIGHT_CENSORED'
        baseline=original.get('CP') or {};relation=None
        if outcome=='EXIT_SIGNAL' and baseline.get('outcome')=='EXIT_SIGNAL':
            relation='PHASE_EARLIER' if exitday<baseline['exit_day'] else 'SAME_SIGNAL_DAY' if exitday==baseline['exit_day'] else 'PHASE_LATER'
        result.append(clean(dict(base,E=E,S=S,P0=P0,threshold_E_plus_2S=E+2*S,outcome=outcome,
            exit_day=exitday,exit_reason=exitreason,exit_line=exitline,
            exit_next_OPEN_reference=None if exitj is None else quote(exitj,exitline,seg[a]),
            first_reached_2S_day=first_reached,phase_switch_day=switched,phase_at_end=phase,
            reached_2S=reached,ever_unknown=ever_unknown,last_unknown_reason=unknown_reason,
            relation_to_saved_CP=relation,steps=steps)))
    return clean(result)
