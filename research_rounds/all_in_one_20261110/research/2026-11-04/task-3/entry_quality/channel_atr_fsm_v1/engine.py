"""Fixed L20/ATR14/one-initial-ATR/N3 market shadows; no account or sizing."""
import hashlib
import json
import math
import numpy as np
import pandas as pd

EPS=4*2**-53/(1-4*2**-53)
N=3.0
def finite(x):
    try:return x is not None and x is not pd.NA and math.isfinite(float(x))
    except (ValueError,TypeError):return False
def positive(x):return finite(x) and float(x)>0
def flag(x):return bool(x) if isinstance(x,(bool,np.bool_)) else None
def bit(x):return int(x) if finite(x) and float(x) in (0.,1.) else None
def ge(a,b):return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
def gt(a,b):return a>b and not ge(b,a)
def source(x):
    if x is None or x is pd.NA:return None
    if isinstance(x,str):return x if x else None
    return str(int(x)) if finite(x) and float(x).is_integer() else str(x) if finite(x) else None
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is None or x is pd.NA:return None
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,pd.Timestamp):return str(x.date())
    return None if isinstance(x,float) and not math.isfinite(x) else x
def key(*x):return hashlib.sha256(json.dumps(clean(x),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def col(df,name):return df[name].to_numpy() if name in df else np.full(len(df),None,dtype=object)


def features(price):
    """Strict-Boolean copy of frozen prior-H/Wilder formula; C validity is separate."""
    if not isinstance(price.index,pd.DatetimeIndex) or not price.index.is_unique or not price.index.is_monotonic_increasing:
        raise ValueError('ordered unique original DatetimeIndex required')
    arrays={k:col(price,k) for k in ['high','low','close','segment_id','price_eligible','observed_bar','synthetic_event_bar','source_invalid']}
    rows=[];segment=None;prev=None;atr=None;trs=[];highs=[]
    for i in range(len(price)):
        seg=source(arrays['segment_id'][i]);changed=seg is not None and seg!=segment
        if changed:segment=seg;prev=None;atr=None;trs=[];highs=[]
        flags=[flag(arrays[k][i]) for k in ['price_eligible','observed_bar','synthetic_event_bar','source_invalid']]
        known=all(x is not None for x in flags)
        eligible=known and flags==[True,True,False,False] and seg is not None
        c=arrays['close'][i];close_valid=bool(eligible and positive(c))
        h,l=arrays['high'][i],arrays['low'][i]
        valid=bool(close_valid and positive(h) and positive(l) and float(h)>=float(c)>=float(l))
        reason='KNOWN' if valid else 'UNKNOWN_SIDE_FLAGS' if not known else 'UNKNOWN_SOURCE' if seg is None else 'INELIGIBLE_OR_SYNTHETIC' if not eligible else 'INVALID_HLC'
        row=dict(valid_bar=valid,close_valid=close_valid,sideflags_known=known,source_key=seg,source_changed=changed,
                 data_status=reason,clean_run_prior_bars=len(highs),TR=None,ATR14=None,ATR14_prior=None,U20=None,
                 z20=None,break20=None,rolloff20=None)
        if not valid:
            prev=None;atr=None;trs=[];highs=[];rows.append(row);continue
        h,l,c=map(float,(h,l,c));ap=atr
        u=max(highs[-20:]) if len(highs)>=20 else None
        oldu=max(highs[-21:-1]) if len(highs)>=21 else None
        tr=h-l if prev is None else max(h-l,abs(h-prev),abs(l-prev))
        trs.append(tr)
        if atr is None and len(trs)>=14:atr=math.fsum(trs[:14])/14.
        elif atr is not None:atr=(13.*atr+tr)/14.
        ready=positive(ap)
        row.update(TR=tr,ATR14=atr,ATR14_prior=ap,U20=u,z20=(c-u)/ap if ready and u is not None else None,
                   break20=gt(c,u) if ready and u is not None else None,
                   rolloff20=(u<oldu) if u is not None and oldu is not None else None)
        rows.append(row);prev=c;highs.append(h)
    return pd.DataFrame(rows,index=price.index)


def grid(diff,scale):
    """Largest j satisfying original gamma4 ge(diff,j*S), not bare float floor."""
    j=max(0,math.floor(max(0.,diff)/scale))
    while ge(diff,(j+1)*scale):j+=1
    while j>0 and not ge(diff,j*scale):j-=1
    return j


def market_fsm(sid,price,events,version,feature_frame=None):
    f=features(price) if feature_frame is None else feature_frame
    e=events.reindex(price.index);fr=f.to_dict('records')
    a={k:col(price,k) for k in ['close','high','raw_close']}
    ev=col(e,'event');piv=col(e,'confirmed_pivot_price');pday=col(e,'confirmed_pivot_date')
    eseg=col(e,'segment_id');leg=col(e,'leg_direction')
    rows=[];out_events=[];generations=[];g=None;ordinal=0;last_source=None
    def emit(kind,day,generation,**data):
        x=dict(kind=kind,day=day,sid=sid,generation_id=generation,event_id=key(version,sid,day,generation,kind),**data)
        out_events.append(clean(x));return x
    def seal(day,reason):
        nonlocal g
        generations.append(clean(dict(g,end_day=day,end_reason=reason)));g=None
    for i,t in enumerate(price.index):
        day=str(t.date());r=fr[i];seg=r['source_key'];C=float(a['close'][i]) if positive(a['close'][i]) else None
        before=None if g is None else dict(g);exits=[];archive=None;start=None;seen=None;advance=None;hard_raise=None
        if seg is not None and last_source is not None and seg!=last_source and g is not None:
            archive=emit('SOURCE_INCOMPARABLE_ARCHIVE',day,g['generation_id'],old_source=last_source,new_source=seg,
                         old_P=g['P'],responsibility_not_filled_or_cleared=True)
            seal(day,'SOURCE_INCOMPARABLE')
        if seg is not None:last_source=seg
        can_compare=bool(r['close_valid'] and g is not None and seg==g['source'])
        if can_compare:
            hard_breach=ge(g['hard'],C)
            if ge(g['P'],C):
                exits.append(emit('EXIT_STORED_LINE',day,g['generation_id'],C=C,P_old=g['P'],hard_old=g['hard'],
                                  hard_breach=hard_breach,reason='HARD_SUPPORT' if hard_breach else 'STORED_ATR_LINE'))
                seal(day,exits[-1]['reason'])
            elif positive(r['ATR14_prior']):
                Q=max(g['P'],g['hard'],g['peak']-N*float(r['ATR14_prior']))
                if ge(Q,C):
                    exits.append(emit('EXIT_NEW_ATR_PROPOSAL',day,g['generation_id'],C=C,P_old=g['P'],Q=Q,
                                      hard_old=g['hard'],peak_before=g['peak'],ATR_prior=r['ATR14_prior'],hard_breach=False))
                    seal(day,'NEW_ATR_PROPOSAL_ALREADY_VIOLATED')
                else:g['P']=Q
        raw_positive=bool(r['close_valid'] and finite(ev[i]) and float(ev[i])==1. and finite(leg[i])
                          and source(eseg[i])==seg and positive(piv[i]) and pday[i] is not None and pd.notna(pday[i])
                          and str(pday[i])[:10]<=day)
        if raw_positive:
            low=float(piv[i])
            if g is None:
                ordinal+=1;gid=key(version,sid,seg,day,ordinal)
                P=max(low,C-N*float(r['ATR14_prior'])) if positive(r['ATR14_prior']) else low
                g=dict(generation_id=gid,source=seg,ordinal=ordinal,start_day=day,start_C=C,hard=low,P=P,peak=C,
                       channel_day=None,A=None,S=None,F=None,j_consumed=0,mature=False,
                       start_low_pivot_day=str(pday[i])[:10],ATR_unprepared_at_start=not positive(r['ATR14_prior']))
                start=emit('E0_START_ELIGIBILITY',day,gid,C=C,hard=low,P=P,shadow_peak=C,
                           pivot_day=str(pday[i])[:10],ATR_unprepared=g['ATR_unprepared_at_start'],requires_CP=False)
            elif gt(low,g['hard']):
                old=g['hard'];g['hard']=low;g['P']=max(g['P'],low)
                hard_raise=emit('RAISE_HARD_FROM_CONFIRMED_LOW',day,g['generation_id'],old_hard=old,new_hard=low,
                                pivot_day=str(pday[i])[:10],does_not_reset_channel=True)
        ready=bool(r['valid_bar'] and positive(r['ATR14_prior']) and positive(r['U20']))
        if g is not None and seg==g['source']:
            if g['channel_day'] is None and ready and gt(C,float(r['U20'])):
                g.update(channel_day=day,A=C,S=float(r['ATR14_prior']),F=C,j_consumed=0)
                seen=emit('CHANNEL_SEEN',day,g['generation_id'],A=C,S=g['S'],U20=r['U20'],z20=r['z20'],
                          rolloff20=r['rolloff20'],mature=False)
            elif g['channel_day'] is not None and g['channel_day']<day and r['close_valid']:
                oldF=g['F'];g['F']=max(oldF,C);j=grid(g['F']-g['A'],g['S'])
                if not ready and j>g['j_consumed']:
                    oldj=g['j_consumed'];g['j_consumed']=j
                    emit('SKIPPED_DATA_UNREADY',day,g['generation_id'],C=C,A=g['A'],S=g['S'],j=j,
                         previous_consumed_j=oldj,old_close_frontier=oldF,permission_issued=False)
                elif ready and start is None and gt(C,oldF) and j>g['j_consumed']:
                    oldj=g['j_consumed'];g['j_consumed']=j;g['mature']=True
                    advance=emit('CHANNEL_ADVANCE',day,g['generation_id'],C=C,A=g['A'],S=g['S'],j=j,
                                 previous_consumed_j=oldj,old_close_frontier=oldF,same_day_channel_break=r['break20'],
                                 no_backlog_permissions=True)
        if g is not None and start is None and r['valid_bar'] and seg==g['source']:
            g['peak']=max(g['peak'],float(a['high'][i]))
        current_known=bool(r['close_valid'] and seg is not None)
        mode='UNKNOWN' if not current_known else 'OFF' if g is None else 'MATURE' if g['mature'] else 'CHANNEL_SEEN' if g['channel_day'] else 'START'
        priority='EXIT_PRIORITY' if exits or archive else 'CHANNEL_ADVANCE' if advance else 'E0_START_ELIGIBILITY' if start else 'CHANNEL_SEEN_FACT_ONLY' if seen else None
        rows.append(clean(dict(sid=sid,day=day,C=C,raw_C=a['raw_close'][i],original_E0_event=ev[i],
            **r,mode=mode,generation_id=None if g is None else g['generation_id'],ordinal=None if g is None else g['ordinal'],
            hard_old=None if before is None else before['hard'],P_old=None if before is None else before['P'],
            shadow_peak_before=None if before is None else before['peak'],
            hard=None if g is None else g['hard'],P_next=None if g is None else g['P'],shadow_peak_next=None if g is None else g['peak'],
            channel_day=None if g is None else g['channel_day'],A=None if g is None else g['A'],S=None if g is None else g['S'],
            close_frontier=None if g is None else g['F'],j_consumed=None if g is None else g['j_consumed'],
            mature_memory=False if g is None else g['mature'],current_mature=None if not current_known else False if g is None else g['mature'],
            E0_start_event=start is not None,CHANNEL_seen=seen is not None,CHANNEL_advance=advance is not None,
            exit_event_count=len(exits),source_archive=archive is not None,exit_and_restart_same_CLOSE=bool(exits and start),
            bundle_priority=priority,bundle_id=None if priority is None else key(version,sid,day,'ONE_BUNDLE'),
            shadow_not_actual_position=True)))
    if g is not None:generations.append(clean(dict(g,end_day=None,end_reason='SOURCE_END_RIGHT_CENSORED')))
    assert len({x['event_id'] for x in out_events})==len(out_events)
    return dict(daily=pd.DataFrame(rows,index=price.index),events=out_events,generations=generations)


def protection_pairs(sid,price,feature_frame,native,cp,anchor_mask,version):
    """All raw anchors retained. Inner protection loops use arrays, never pandas.loc."""
    f=feature_frame;n=native.reindex(price.index);c=cp.reindex(price.index)
    days=np.array([str(t.date()) for t in price.index]);length=len(days)
    C=col(price,'close');H=col(price,'high');O=col(price,'open');rawO=col(price,'raw_open')
    fv=col(f,'valid_bar');cv=col(f,'close_valid');seg=col(f,'source_key');atr=col(f,'ATR14_prior')
    I=col(n,'i_target');IF=col(n,'i_floor');receipt=col(c,'receipt');candidate=col(c,'candidate')
    nextobs=np.full(length,-1,dtype=np.int64);nxt=-1
    for j in range(length-1,-1,-1):
        nextobs[j]=nxt
        if fv[j] is True or isinstance(fv[j],np.bool_) and bool(fv[j]):nxt=j
    def quote_after(j,line,anchor_source):
        k=int(nextobs[j])
        if k<0:return dict(next_observation_day=None,OPEN=None,raw_OPEN=None,OPEN_minus_line=None,quote_status='NO_NEXT_OBSERVATION')
        if seg[k]!=anchor_source or not positive(O[k]):return dict(next_observation_day=days[k],OPEN=None,raw_OPEN=None,OPEN_minus_line=None,quote_status='UNKNOWN_OR_INCOMPARABLE')
        return dict(next_observation_day=days[k],OPEN=float(O[k]),raw_OPEN=clean(rawO[k]),OPEN_minus_line=float(O[k])-line,
                    quote_status='REFERENCE_ONLY_NOT_EXECUTABLE_FILL')
    pairs=[]
    for a in np.flatnonzero(np.asarray(anchor_mask,dtype=bool)):
        base=dict(sid=sid,anchor_day=days[a],anchor_id=key(version,sid,days[a],'ORIGINAL_RAW_CP_ANCHOR'),
                  original_candidate=clean(candidate[a]),original_I_floor=clean(IF[a]),
                  anchor_C=clean(C[a]),anchor_ATR_prior=clean(atr[a]),
                  position_or_fill_claim=False,mature_or_V5_identity='NOT_ASSIGNED')
        if not fv[a] or not positive(candidate[a]) or not positive(IF[a]) or bit(I[a])!=1:
            pairs.append(dict(base,status='ANCHOR_INPUT_UNKNOWN_OR_I_INVALID',CP=None,ATR3=None));continue
        P0=max(float(candidate[a]),float(IF[a]));base['P0']=P0
        if not positive(atr[a]):
            pairs.append(dict(base,status='ANCHOR_ATR_UNPREPARED',CP=None,ATR3=None));continue
        S=float(atr[a]);base['common_risk_denominator_ATR']=S
        if ge(P0,float(C[a])):
            pairs.append(dict(base,status='ANCHOR_PROTECTION_AT_OR_ABOVE_CLOSE',CP=None,ATR3=None));continue
        # Determine common future independently from either branch's stop.
        future=[];common_end_reason='SOURCE_END';common_end_day=days[-1]
        for j in range(a+1,length):
            if seg[j]!=seg[a]:common_end_reason='SOURCE_INCOMPARABLE';common_end_day=days[j];break
            if not cv[j] or bit(I[j]) is None:
                common_end_reason='UNKNOWN_DATA_OR_I';common_end_day=days[j];break
            future.append(j)
            if bit(I[j])==0:common_end_reason='ORIGINAL_I_INVALID';common_end_day=days[j];break
            if not fv[j]:common_end_reason='UNKNOWN_HLC';common_end_day=days[j];break
        futureC=[float(C[j]) for j in future]
        common_max=max([float(C[a])]+futureC) if future else None
        base.update(common_end_reason=common_end_reason,common_end_day=common_end_day,common_observations=len(future),
                    common_max_close=common_max,common_favorable_excursion_ATR=None if common_max is None else (common_max-float(C[a]))/S,
                    strong_decile='NOT_ASSIGNED_REQUIRES_FULL_WINDOW_COHORT')
        entry=int(nextobs[a])
        if entry<0 or seg[entry]!=seg[a] or not positive(O[entry]):
            pairs.append(dict(base,status='ENTRY_QUOTE_UNKNOWN',entry_reference=quote_after(a,P0,seg[a]),CP=None,ATR3=None));continue
        if ge(P0,float(O[entry])):
            pairs.append(dict(base,status='ENTRY_QUOTE_INVALID',entry_reference=quote_after(a,P0,seg[a]),CP=None,ATR3=None));continue
        base['entry_reference']=quote_after(a,P0,seg[a])
        branches={}
        for label in ['CP','ATR3']:
            P=P0;peak=float(C[a]);close_peak=float(C[a]);peak_while_alive=float(C[a]);held=0;exitj=None;exit_reason=None;exit_line=None
            twenty=None;post20n=0;post20dd=None;unknown=None
            for j in future:
                held+=1;priceC=float(C[j]);oldP=P;oldpeak=peak
                close_peak=max(close_peak,priceC);peak_while_alive=max(peak_while_alive,priceC)
                if held>20:
                    post20n+=1;dd=(close_peak-priceC)/S;post20dd=dd if post20dd is None else max(post20dd,dd)
                if bit(I[j])==0:exit_reason='ORIGINAL_I_INVALID';exit_line=P
                elif ge(P,priceC):exit_reason='EXIT_STORED_LINE';exit_line=P
                elif not fv[j]:unknown='UNKNOWN_HLC_AFTER_OLD_LINE_CHECK';break
                elif not positive(IF[j]):unknown='UNKNOWN_ORIGINAL_I_FLOOR';break
                elif label=='CP':
                    proposal=max(P,float(IF[j]))
                    if flag(receipt[j]) is True:
                        if not positive(candidate[j]):unknown='UNKNOWN_ORIGINAL_CP_CANDIDATE';break
                        proposal=max(proposal,float(candidate[j]))
                    if ge(proposal,priceC):exit_reason='EXIT_NEW_CP_OR_I_PROPOSAL';exit_line=proposal
                    else:P=proposal
                elif not positive(atr[j]):unknown='ATR_PRIOR_UNPREPARED_DURING_SHADOW';break
                else:
                    proposal=max(P,float(IF[j]),oldpeak-N*float(atr[j]))
                    if ge(proposal,priceC):exit_reason='EXIT_NEW_ATR_PROPOSAL';exit_line=proposal
                    else:P=proposal
                if held==20:
                    twenty=dict(day=days[j],status='EXIT_AT_20' if exit_reason else 'ALIVE_AT_20',P_old=oldP,
                                P_after=None if exit_reason else P,C=priceC,stop_distance_ATR=None if exit_reason else (priceC-P)/S)
                if exit_reason:exitj=j;break
                peak=max(peak,float(H[j]))
            if exitj is not None:
                status20='EXIT_BEFORE_20' if held<20 else twenty['status'] if held==20 else 'ALIVE_AT_20'
                outcome='EXIT_SIGNAL'
            else:
                is_unknown=bool(unknown or common_end_reason.startswith('UNKNOWN'))
                status20='UNKNOWN_BEFORE_20' if is_unknown and held<20 else 'RIGHT_CENSORED_BEFORE_20' if held<20 else 'UNKNOWN_AT_20' if unknown and held==20 else 'ALIVE_AT_20'
                outcome='UNKNOWN' if is_unknown else 'RIGHT_CENSORED'
            branches[label]=dict(outcome=outcome,exit_day=None if exitj is None else days[exitj],exit_reason=exit_reason,
                exit_signal_C=None if exitj is None else float(C[exitj]),exit_line=exit_line,
                effective_observations_held=held,status_at20=status20,twentieth_observation=twenty,
                post20_observations=post20n,post20_max_close_drawdown_ATR=post20dd if post20n else None,
                common_peak_after_shadow_truncation_ATR=None if common_max is None or exitj is None else max(0.,common_max-peak_while_alive)/S,
                next_observation_quote=None if exitj is None else quote_after(exitj,exit_line,seg[a]),
                unknown_reason=unknown,censor_reason=None if exitj is not None else unknown or common_end_reason,
                peak_initialization='COMMON_SIGNAL_CLOSE_NOT_ANCHOR_HIGH',no_price_return_or_PnL=True)
        pairs.append(dict(base,status='PAIRED_SHADOWS',**branches))
    return clean(pairs)
