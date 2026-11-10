"""Two fixed-opening input/minimum-size previews only; NOT a batch allocator.
No Account/Contract is constructed, no receipt is consumed, no order is placed,
and no historical account is advanced. The original pure LR.preview is reused.
"""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace
import json,gzip,collections,sys,time,hashlib
import pandas as pd

O=Path(__file__).resolve().parent; W=O.parent
sys.path.insert(0,str(W/'case-stage-ledger-20261031/v3'))
import joint_v3 as J

def read(p):return json.loads(Path(p).read_text())
def book(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def stream(p):
    with gzip.open(p,'rt') as f:
        for s in f:yield json.loads(s)
def save(name,x):
    p=O/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)

begun=time.monotonic()
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};FACTORS={}
def factor(sid,at):
    # The native four-quarter interface has no 2022/23 facts. Use the exact
    # full-warm cache actually supplied to these saved reference accounts.
    if sid not in FACTORS:FACTORS[sid]=pd.read_parquet(SM[sid]['refs']['facts'],columns=['factor'])
    f=FACTORS[sid];d=pd.Timestamp(at.date());assert d in f.index,(sid,d,'fullwarm factor missing')
    return D(str(f.loc[d,'factor']))
roots={'2023-01-20':W/'recovery-2023-readiness-20261101/runs/Bdiag/pair'}
weak=W/'2022-normal-reference-20261031/runs/B_diag/pair'
counts=collections.Counter()
for x in stream(weak/'funding.jsonl.gz'):
    if '09:30:' in x['at'] and 'probe_risk' in x.get('result',''):
        counts[x['at'][:10]]+=1
weakday=min(counts,key=lambda d:(-counts[d],d));assert weakday=='2022-06-29'
roots[weakday]=weak; cases={};allids=set()
for at,root in roots.items():
    b=book(root/'B.json.gz')
    dec=max((x for x in b['decisions'] if x['at'][:10]<at),key=lambda x:x['at'])
    fund=[x for x in stream(root/'funding.jsonl.gz') if x['at'][:10]==at and '09:30:' in x['at']]
    reserve=[x for x in b['journal'] if x['kind']=='real_reserve' and str(x['at'])[:10]==at]
    cases[at]=(root,dec,fund,reserve)
    allids.update(x['sid'] for x in dec['intents'])
load=time.monotonic()
_,market,facts=J.M.context('2023-01-20',ids=sorted(allids))
market_seconds=time.monotonic()-load
out=[]
for at,(root,dec,fund,reserve) in cases.items():
    decision=J.M.N.iso(dec['at'].replace(' ','T')); opening=J.M.N.iso(at+'T09:30:00+08:00')
    quotes=market.quotes(decision,ids={i['sid'] for i in dec['intents']})
    last={(x['sid'],x['role']):x for x in fund}
    accepted={(x['sid'],x['role']):x for x in reserve}
    rows=[];unknown=[]
    for src in sorted(dec['intents'],key=lambda i:(i['rank'],i['role']!='core')):
        sid=src['sid'];quote=quotes.get(sid)
        if quote is None:unknown.append(dict(sid=sid,role=src['role'],why='original dated decision quote unavailable'));continue
        i=dict(src)
        for k in ('floor','budget','risk_budget'):
            if k in i:i[k]=D(str(i[k]))
        i['quote']=quote
        raw=market.raw[sid]; d=pd.Timestamp(at)
        if d not in raw.index or pd.isna(raw.loc[d,'open']) or raw.loc[d,'open']<=0:
            unknown.append(dict(sid=sid,role=i['role'],why='original opening price unavailable'));continue
        x,why=J.LR.preview(i,D(str(raw.loc[d,'open'])),factor(sid,opening),market.quantity(sid,opening),market.fees(sid,opening))
        r=dict(sid=sid,role=i['role'],rank_zero_based=i['rank'],original_H1=i['score'],original_independent_cap=i['cap'],original_independent_budget=i['budget'],original_funding_result=last.get((sid,i['role'])),original_actual_reservation=accepted.get((sid,i['role'])),independent_preview_reason=why)
        if x:
            q=x['minq'];p=x['price'];fl=x['floor'];fee=J.LR.fees(q,p,x['schedule'],'buy',quote.par_value)
            r.update(minimum_shares=q,subsequent_order_increment=x['rule'].buy_step,matching_increment=x['rule'].fill_step,
                original_independent_maximum=x['maxq'],minimum_gross=D(q)*p,minimum_buy_fee=fee,
                minimum_nominal_risk=D(q)*max(D(0),p-fl),
                minimum_core_protection_risk=J.LR.protection_risk(q,p,fl,x['schedule'],quote.par_value) if i['role']=='core' else None,
                fraction_of_reference_probe_risk_budget=D(q)*max(D(0),p-fl)/(D(dec['nav'])*D('.005')),
                reference_budget_basis='previous decision NAV only; not an assertion of exact live fee-adjusted admission',
                full_target_gross=D(x['maxq'])*p,full_target_fee=J.LR.fees(x['maxq'],p,x['schedule'],'buy',quote.par_value))
            ar=accepted.get((sid,i['role']))
            if ar:
                r['actually_reserved_quantity']=ar['shares']
                r['actual_reserved_is_already_minimum']=ar['shares']==q
                r['risk_reduction_if_only_this_original_order_shrunk_to_minimum']=D(ar['shares']-q)*max(D(0),p-fl)
        rows.append(r)
    relevant=[x for x in rows if (x.get('original_actual_reservation') or {}).get('pool')=='probe']
    fullsmall=[x for x in relevant if x.get('actual_reserved_is_already_minimum')]
    valid=[x for x in rows if x.get('original_independent_maximum')]
    core=[x for x in rows if x['role']=='core'];mobile=[x for x in rows if x['role']=='mobile']
    out.append(dict(opening=at,decision_day=dec['at'][:10],policy='unchanged saved Bdiag',
        weak_date_selection='max count of original opening funding rows containing probe_risk, then earliest date; no price/PnL selection' if at==weakday else 'previously fixed Jan20 opening',
        original_probe_rejection_rows=counts[at] if at==weakday else sum('probe_risk' in x.get('result','') for x in fund),
        pending_role_intents=len(dec['intents']),distinct_stocks=len({x['sid'] for x in dec['intents']}),
        both_roles_stocks=len({x['sid'] for x in core}&{x['sid'] for x in mobile}),
        independent_preview_passed=len(valid),independent_preview_rejected=len(rows)-len(valid),unknown=unknown,
        original_actual_probe_reservations=len(relevant),already_minimum_probe_reservations=len(fullsmall),
        original_probe_reserved_risk=sum((D(x['actually_reserved_quantity'])*D(x['minimum_nominal_risk'])/D(x['minimum_shares']) for x in relevant),D(0)),
        shrink_only_risk_release_upper_bound=sum((D(x['risk_reduction_if_only_this_original_order_shrunk_to_minimum']) for x in relevant),D(0)),
        independent_minimum_risk_over_reference_20pct_of_probe=sum(x['fraction_of_reference_probe_risk_budget']>=D('.2') for x in valid),
        independent_minimum_risk_over_reference_50pct_of_probe=sum(x['fraction_of_reference_probe_risk_budget']>=D('.5') for x in valid),
        rows=rows,
        not_a_two_pass_allocation=True,new_footholds_or_downsizes_not_estimated=True,
        limitation='Baseline-dependent orders/route sets are not an alternative batch. Exact new footholds require a separately reviewed full-batch shadow-resource planner including failed/suppressed roles and migration side effects. No shared capacity is relaxed.'))
    save(at+'_MINIMUM_INPUT_PREVIEW.json',out[-1])
save('PREVIEW_SUMMARY.json',dict(passed=True,new_accounts=0,new_orders=0,receipt_consumptions=0,
    new_account_progression=False,new_batch_allocator_implemented=False,seconds=time.monotonic()-begun,
    readonly_native_market_load_seconds=market_seconds,dates=[{k:v for k,v in r.items() if k!='rows'} for r in out]))
print('STATIC_MINIMUM_INPUT_PREVIEWS',round(time.monotonic()-begun,3),'seconds',[(x['opening'],x['pending_role_intents'],x['original_actual_probe_reservations'],x['already_minimum_probe_reservations']) for x in out],flush=True)
