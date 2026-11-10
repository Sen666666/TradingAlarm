"""Read saved JSON only. Rebuild line-risk and lock/pending charges, no imports from engine."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
import json, gzip, hashlib, csv

getcontext().prec = 28
OUT=Path(__file__).resolve().parent
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0)

def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())

def dump(name,x):
    (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

def rebuild(p,variant):
    j=read(p);a=j['account'];b=a['balance'];live=[z for z in a['layers'] if z['qty']]
    group=defaultdict(lambda:defaultdict(lambda:Z));tot=defaultdict(lambda:Z);details=[]
    for k in ('principal','giveback','line','lock_extra','risk','capital'):tot[k]=Z
    for z in live:
        sid=z['sid'];q=D(z['qty']);meta=a['capital_meta'][str(z['id'])]
        mark=D(a['market_marks'][sid]);factor=D(a['market_factors'][sid]);cost=D(meta['unit_cost'])
        floor=D(a['facts_floors'][sid] if meta['role']=='core' else z['floor'])/factor
        principal=q*max(Z,min(mark,cost)-floor)
        giveback=q*max(Z,mark-max(cost,floor));line=q*max(Z,mark-floor)
        assert abs(principal+giveback-line)<D('1e-20')
        locked=Z;lockrisk=Z
        for e in a['policy']['locks'].values():
            if e['lot']!=z['id'] or not e['remaining']:continue
            rem=D(e['remaining']);locked+=rem
            assert e['e0'] is not None and e['q0'] is not None and D(e['ratio'])>0
            lockrisk+=max(rem*max(Z,mark-floor),D(e['e0'])*rem/(D(e['ratio'])*D(e['q0'])))
        assert locked<=q
        risk=(q-locked)*max(Z,mark-floor)+lockrisk
        extra=risk-line
        assert extra>=D('-1e-20')
        # Decimal grouping can leave <1e-20 arithmetic noise; don't alter charge.
        item=dict(layer=z['id'],sid=sid,role=meta['role'],qty=q,mark=mark,cost=cost,floor=floor,
            principal=principal,giveback=giveback,line=line,lock_extra=extra,risk=risk,capital=q*mark,
            I_valid=a.get('funding_stock_I',{}).get(sid),locked_qty=locked)
        details.append(item)
        for target in (tot,group[meta['role']]):
            for k in ('principal','giveback','line','lock_extra','risk','capital'):target[k]+=item[k]
    pending=Z;pendingcap=Z
    for sid,o in a['buys'].items():
        support=a['supports'][o['order_id']];im=a['order_meta'][o['order_id']]
        floor=D(im['floor'])/D(a['market_factors'][sid]);pending+=D(o['remaining_shares'])*max(Z,D(support['limit'])-floor)
        pendingcap+=D(o['remaining_budget_cny'])
    tot['pending_risk']=pending;tot['pending_capital']=pendingcap
    tot['total_risk']=tot['risk']+pending;tot['total_capital']=tot['capital']+pendingcap
    bridge=next(e['bridge'] for e in reversed(j['events']) if e['phase']=='CLOSE')
    assert abs(tot['total_risk']-D(bridge['resources']['risk']))<D('1e-16'),(p,tot,bridge['resources'])
    assert abs(tot['total_capital']-D(bridge['resources']['capital']))<D('1e-16')
    assert abs(tot['capital']-D(b['inventory']))<D('1e-16')
    nav=D(b['nav']);tot['nav']=nav;tot['risk_pct_nav']=tot['total_risk']/nav*100
    tot['principal_pct_of_line']=tot['principal']/tot['line']*100 if tot['line'] else None
    tot['giveback_pct_of_line']=tot['giveback']/tot['line']*100 if tot['line'] else None
    tot['capital_pct_nav']=tot['capital']/nav*100
    return dict(day=p.name[:10],variant=variant,source=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        totals=dict(tot),roles={k:dict(v) for k,v in group.items()},live_lots=len(live),details=details)

def aggregate(rows):
    sums=defaultdict(lambda:Z)
    for r in rows:
        for k in ('principal','giveback','line','lock_extra','risk','pending_risk','total_risk','capital','nav'):
            sums[k]+=r['totals'][k]
    return dict(observations=len(rows),first=rows[0]['day'],last=rows[-1]['day'],equal_observation_risk_yuan_sum=dict(sums),
        principal_share_of_line_pct=sums['principal']/sums['line']*100 if sums['line'] else None,
        giveback_share_of_line_pct=sums['giveback']/sums['line']*100 if sums['line'] else None,
        lock_extra_share_total_pct=sums['lock_extra']/sums['total_risk']*100 if sums['total_risk'] else None,
        days_risk_above_6pct=sum(r['totals']['risk_pct_nav']>6 for r in rows),
        mean_risk_pct=sum((r['totals']['risk_pct_nav'] for r in rows),Z)/len(rows),
        mean_exposure_pct=sum((r['totals']['capital_pct_nav'] for r in rows),Z)/len(rows))

def main():
    specs=[('C10_2025Jul','g-s-C-month-continuation-20261102/runs/2025_26-C10'),
        ('C10_2025Aug','g-s-C-August-continuation-v1-20261102/runs/C10'),
        ('C10_2022Jan_early','g-s-C-month-continuation-20261102/runs/2022-C10'),
        ('C10_R0_2022Jan_late','g-s-C-R0-continuous-january-v1-20261102/runs/C10')]
    rows=[];seen=set()
    for label,directory in specs:
        for p in sorted((ROOT/directory).glob('*-CLOSE.json*')):
            # R0 January is a different policy and remains separate.
            r=rebuild(p,label);key=(label,r['day']);assert key not in seen;seen.add(key);rows.append(r)
        print(label,'complete',len([r for r in rows if r['variant']==label]),flush=True)
    summaries={label:aggregate([r for r in rows if r['variant']==label]) for label,_ in specs}
    dump('DAILY_RISK_DECOMPOSITION.json',rows);dump('RISK_SUMMARY.json',dict(summaries=summaries,financial_events=0,
        reads_saved_JSON_only=True,fees_excluded_from_cost_reference=True,cost_reference='actual gross native unit_cost adjusted by actual splits',
        identity='principal+giveback=line; plus execution lock excess and pending risk equals saved original bridge',
        sampling='saved daily CLOSE observations, equal observation weights; not future counterfactual risk or avoidable loss'))
    with (OUT/'DAILY_RISK_DECOMPOSITION.csv').open('w') as f:
        cols=['variant','day','principal','giveback','lock_extra','pending_risk','total_risk','risk_pct_nav','principal_pct_of_line','capital_pct_nav']
        w=csv.DictWriter(f,cols);w.writeheader()
        for r in rows:w.writerow(dict(variant=r['variant'],day=r['day'],**{k:r['totals'][k] for k in cols[2:]}))
    print(json.dumps(summaries,default=str,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
