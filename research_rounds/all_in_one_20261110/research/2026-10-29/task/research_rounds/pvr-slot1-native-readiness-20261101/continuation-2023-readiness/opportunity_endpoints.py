"""Competing observed funding, industry-attempt end, observation cutoff.

No account or strategy calls. Attempt ending is an authorization endpoint,
not proof that a held position was sold. A completed fill wins an exact tie;
an end known at the cutoff is observed termination, not right-censoring.
"""
from datetime import datetime
from collections import Counter
CUTOFF='2023-12-29'
def atclose(day):return datetime.fromisoformat(day+'T15:10:00+08:00')
def endpoint(fill_at,end_day,cutoff=CUTOFF):
    end=atclose(end_day) if end_day else None;cut=atclose(cutoff)
    fill=datetime.fromisoformat(fill_at) if fill_at else None
    events=[(cut,2,'observation_cutoff_still_active')]
    if fill is not None and fill<=cut:events.append((fill,0,'funded_before_attempt_end'))
    if end is not None and end<=cut:events.append((end,1,'industry_attempt_ended_before_funding'))
    t,_,status=min(events)
    return dict(status=status,endpoint_at=t.isoformat(),
        later_funding_after_attempt_end=bool(fill and end and end<fill<=cut),
        tie_policy='completed_fill_first_at_exact_timestamp;industry_end_before_observation_cutoff')
def annotate(g,states,calendar):
    g=dict(g);ss=states[g['sector']];first=g['first_market_eligible'];aid=g['market_attempt']
    dates=[d for d in calendar if first<=d<=CUTOFF]
    assert dates and all(d in ss for d in dates),'unknown industry observation cannot be called active'
    end=next((d for d in dates if not ss[d]['E0_valid'] or ss[d]['attempt_id']!=aid),None)
    if end is None:assert ss[dates[-1]]['E0_valid'] and ss[dates[-1]]['attempt_id']==aid
    g['industry_attempt_end_observation']=end
    g['industry_attempt_end_known_at']=atclose(end).isoformat() if end else None
    g['mobile_funding_endpoint']=endpoint(g.get('first_actual_mobile_fill'),end)
    if 'first_actual_anyrole_new_buy' in g:g['anyrole_funding_endpoint']=endpoint(g['first_actual_anyrole_new_buy'],end)
    g['no_observed_mobile_funding']=g.get('first_actual_mobile_fill') is None
    g['no_observed_anyrole_new_buy']=g.get('first_actual_anyrole_new_buy') is None
    g.pop('never_funded_right_censored',None);g.pop('no_later_new_buy_right_censored',None)
    g['industry_attempt_inherited_before_window']=g.pop('attempt_inherited_left_censor',g.get('industry_attempt_inherited_before_window',False))
    return g
def summarize(groups,field):
    counts=Counter(g[field]['status'] for g in groups)
    assert sum(counts.values())==len(groups)
    return dict(groups=len(groups),funded_before_attempt_end=counts['funded_before_attempt_end'],
        industry_attempt_ended_before_funding=counts['industry_attempt_ended_before_funding'],
        still_active_at_observation_cutoff_right_censored=counts['observation_cutoff_still_active'],
        later_funding_after_termination=sum(g[field]['later_funding_after_attempt_end'] for g in groups))
