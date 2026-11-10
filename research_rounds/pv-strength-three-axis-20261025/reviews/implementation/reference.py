"""Independent, protocol-led PVS-B2 reference for implementation audit only.

This file never imports the production model.  It uses explicit dictionaries and
math.fsum rather than the model's classes/numpy regressions.  No accounts or I/O.
"""
from copy import deepcopy
from math import fsum, isfinite, log, sqrt, exp, nan
from statistics import median
import pandas as pd


def tolerance(a,b):
    """NUMERICAL_V1.md: only inclusive threshold/standardized tie comparisons."""
    return 32*(2.0**-52)*max(1.0,abs(a),abs(b))


def ge(a,b):
    return a >= b-tolerance(a,b)


def union(intervals):
    edges = sorted([(a, 1) for a, b in intervals if a < b] +
                   [(b, -1) for a, b in intervals if a < b])
    total = 0.0
    parts = active = 0
    last = None
    # Group equal coordinates so touching intervals remain one component.
    points = {}
    for x, delta in edges:
        points[x] = points.get(x, 0) + delta
    for x, delta in sorted(points.items()):
        if active and last is not None:
            total += x - last
        was = active
        active += delta
        if not was and active:
            parts += 1
        last = x
    return total, parts


def structure_initial(p, t, sigma):
    return dict(d=0, serial=0, episode=0, lo=p, hi=p, lot=t, hit=t,
                lod=2*sigma, hid=2*sigma, A=nan, E=nan, S=nan, K=nan,
                pivot=nan, pivot_t=t, Et=t, delta=2*sigma, esigma=sigma,
                born=t, progress=t, advances=0)


def structure_step(s, p, t, sigma, r):
    """Return daily state plus a new independent dictionary; no in-place caller edit."""
    s = deepcopy(s)
    old = deepcopy(s)
    z = dict(pre_direction=float(old['d']), pre_episode=float(old['episode']),
             structure_broken=0., structure_created=0., pivot_confirmed=0.,
             old_retention_at_t=nan, old_support=nan,
             adverse_pre_sigma=(max(0., -old['d']*(p-old['E']))/old['esigma']
                                if old['d'] else nan))

    def start(d, origin, when):
        s.update(d=d, serial=s['serial']+1, episode=s['serial']+1,
                 A=origin, S=origin, E=p, Et=t, delta=2*sigma, esigma=sigma,
                 born=t, progress=t, advances=0, K=nan, pivot=nan)
        z['structure_created'] = 1.

    if old['d'] and old['d']*(p-old['S']) <= 0:
        z.update(structure_broken=1., old_support=old['S'],
                 old_retention_at_t=(p-old['A'])/(old['E']-old['A']))
        s.update(d=0, episode=0, K=nan, pivot=nan, lo=min(p,old['E']),
                 hi=max(p,old['E']), lot=t, hit=t, lod=2*sigma, hid=2*sigma)
        if old['E'] < p:
            s.update(lot=old['Et'], lod=old['delta'])
        elif old['E'] > p:
            s.update(hit=old['Et'], hid=old['delta'])
        if ge(-old['d']*(p-old['E']),old['delta']):
            start(-old['d'], old['E'], old['Et'])
    elif old['d']:
        d = old['d']
        if isfinite(s['K']):
            if d*p < d*s['pivot']:
                s.update(pivot=p, pivot_t=t)
            if d*(p-s['K']) >= 0:
                z['pivot_confirmed'] = 1.
                if d*(s['pivot']-s['S']) > 0:
                    s.update(S=s['pivot'], advances=s['advances']+1, progress=t)
                s.update(K=nan, pivot=nan)
        if d*(p-s['E']) > 0:
            s.update(E=p, Et=t, delta=2*sigma, esigma=sigma, progress=t)
        if not isfinite(s['K']) and ge(-d*(p-s['E']),s['delta']):
            s.update(K=s['E'], pivot=p, pivot_t=t)
    else:
        if p < s['lo']:
            s.update(lo=p, lot=t, lod=2*sigma)
        if p > s['hi']:
            s.update(hi=p, hit=t, hid=2*sigma)
        choices = {1:(p-s['lo'])/s['lod'], -1:(s['hi']-p)/s['hid']}
        eligible={1:ge(p-s['lo'],s['lod']), -1:ge(s['hi']-p,s['hid'])}
        d = 0
        if eligible[1] and eligible[-1]:
            if abs(choices[1]-choices[-1]) <= tolerance(choices[1],choices[-1]):
                d = (r > 0) - (r < 0)
            else:
                d = max(choices, key=choices.get)
        elif eligible[1]:
            d = 1
        elif eligible[-1]:
            d = -1
        if d:
            start(d, s['lo'] if d == 1 else s['hi'], s['lot'] if d == 1 else s['hit'])
    z.update(direction=float(s['d']), episode=float(s['episode']))
    if s['d']:
        span = s['d']*(s['E']-s['A'])
        ret = s['d']*(p-s['A'])/span
        z.update(retention=ret, signed_retention=100*s['d']*ret,
                 span_log_pct=100*span, episode_age=float(t-s['born']),
                 progress_age=float(t-s['progress']), support_advances=float(s['advances']),
                 origin=s['A'], extreme=s['E'], support=s['S'], checkpoint=s['K'])
    return s, z


def ledger_step(events, serial, p, prev, t, sigma, activity, episode, joint):
    """Persistent event map: discard only fully recovered intervals, never restart IDs."""
    result = {}
    for identity, original in events.items():
        e = dict(original)
        e['lo'] = max(e['lo'],p) if e['d'] == -1 else e['lo']
        e['hi'] = min(e['hi'],p) if e['d'] == 1 else e['hi']
        if e['lo'] < e['hi']:
            result[identity] = e
    created = 0.
    if ge(abs(p-prev),sigma) and (not joint or ge(activity,2)):
        serial += 1
        created = 1. if p > prev else -1.
        result[serial] = dict(d=int(created), lo=min(p,prev), hi=max(p,prev),
                              birth=t, episode=episode)
    z = dict(impulse_created=created)
    for d, name in [(-1,'down'), (1,'up')]:
        ee = [e for e in result.values() if e['d'] == d]
        length, count = union([(e['lo'],e['hi']) for e in ee])
        z.update({name+'_zone_log_pct':100*length, name+'_zone_sigma':length/sigma,
                  name+'_events':float(len(ee)), name+'_union_parts':float(count),
                  'oldest_'+name+'_age':float(t-min(e['birth'] for e in ee)) if ee else nan})
    return result, serial, z


def reference_valid(frame, joint=True):
    prices = frame.close.tolist()
    p = [log(x/prices[0]) for x in prices]
    r = [nan] + [b-a for a,b in zip(p[:-1],p[1:])]
    v = frame.volume.tolist()
    rows = []
    s = None
    events = {}
    serial = 0
    for t in range(len(frame)):
        z = {}
        if t >= 64:
            sigma = max(sqrt(fsum(q*q for q in r[t-63:t])/63), 1e-8)
            activity = v[t]/median(v[t-21:t])
            z.update(sigma=sigma, activity=activity, shock=r[t]/sigma, init=float(t==64))
            for h in (5,21):
                xx = [j-h/2 for j in range(h+1)]
                beta = fsum(x*q for x,q in zip(xx,p[t-h:t+1]))/fsum(x*x for x in xx)
                z.update({'speed_'+str(h):beta, 'pace_'+str(h):sqrt(h)*beta/sigma,
                          'amplitude_'+str(h):100*h*beta,
                          'return_'+str(h)+'_log_pct':100*(p[t]-p[t-h])})
            if s is None:
                s = structure_initial(p[t],t,sigma)
                z.update(direction=0., episode=0., pre_direction=0., pre_episode=0.,
                         structure_broken=0., structure_created=0., pivot_confirmed=0.)
            else:
                s, zz = structure_step(s,p[t],t,sigma,r[t])
                z.update(zz)
            z['opposition'] = max(0.,-z['pre_direction']*z['shock']) if z['pre_direction'] else nan
            events, serial, zz = ledger_step(events,serial,p[t],p[t-1],t,sigma,activity,int(z['episode']),joint)
            z.update(zz)
        rows.append(z)
    out = pd.DataFrame(rows, index=frame.index)
    for k in ('origin','extreme','support','checkpoint','old_support'):
        if k in out:
            out[k+'_price'] = [prices[0]*exp(q) if isfinite(q) else nan for q in out[k]]
    return out


def reference_frame(frame, joint=True):
    """Whole invalid rows are unknown; segments independently warm up."""
    out = pd.DataFrame(index=frame.index)
    for segment in dict.fromkeys(frame.segment_id):
        f = frame.loc[(frame.segment_id == segment) & frame.valid_strength_observation]
        if len(f):
            r = reference_valid(f,joint)
            out = out.reindex(columns=out.columns.union(r.columns,sort=False))
            out.loc[r.index,r.columns] = r
    return out
