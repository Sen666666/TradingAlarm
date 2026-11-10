"""Bounded eight-lens review of saved2023 books, no account/indicator replay."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,sys,hashlib
import pandas as pd
import analyze_continuation as C
O,P,W,A,B=C.O,C.P,C.W,C.A,C.B;Z=D(0);OUT=O/'causal-review-2023'
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def n(x):return D(str(x))
def save(p,x):
    p=OUT/p;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def agg(ls):return C.M.contribution(ls)

def review(ref,root,caseids):
    b=C.book(root/'pair/B.json.gz');layers=read(O/'analysis-2023'/ref/'LAYERS_ALL.json');new=read(O/'analysis-2023'/ref/'LAYERS_NEW2023.json')
    for x in layers+new:
        for k in ('cost','net','value'):x[k]=n(x[k])
    ds=rows(root/'pair/daily.jsonl.gz');dm={x['at'][:10]:x for x in ds};actions=B.entry_actions(dict(book=b,layers=layers));am={x['layer']:x for x in actions}
    exitrows=B.exit_chain(dict(book=b,layers=layers,byday=dm));exitmap={x['layer']:x for x in exitrows}
    groups=[]
    for key,fun in [('actual_buy_quarter',lambda x:str(pd.Timestamp(x['opened'][:10]).to_period('Q'))),
                    ('actual_exit_quarter',lambda x:str(pd.Timestamp(x['closed'][:10]).to_period('Q')) if x['closed'] else 'open'),
                    ('industry',lambda x:x['industry']),('action',lambda x:am[x['layer']]['action']),
                    ('role_pool',lambda x:x['role']+'/'+x['pool_at_fill']),
                    ('role_pool_action',lambda x:x['role']+'/'+x['pool_at_fill']+'/'+am[x['layer']]['action']),
                    ('role_pool_first_exit_reason',lambda x:x['role']+'/'+x['pool_at_fill']+'/'+exitmap.get(x['layer'],{}).get('reason','unknown'))]:
        v=collections.defaultdict(list)
        for x in new:v[fun(x)].append(x)
        groups.append(dict(grouping=key,groups=[dict(key=k,**agg(ls)) for k,ls in sorted(v.items(),key=lambda z:sum((n(x['net']) for x in z[1] if n(x['net'])<0),Z))]))
    save(Path(ref)/'LOSS_GROUPS.json',groups)
    selected={s for s in caseids};ops={(x['sid'],x['day']):x for x in rows(root/'pair/opportunities.jsonl.gz') if x['sid'] in selected and x['day'].startswith('2023')}
    states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    facts={s:pd.read_parquet(A.SM[s]['refs']['facts']) for s in selected};pvr={s:pd.read_parquet(O/'scores'/(s+'.parquet')) for s in selected}
    bydecision={(i['sid'],d['at'][:10],i['role']):i for d in b['decisions'] if d['at'].startswith('2023') for i in d['intents'] if i['sid'] in selected}
    ld={x['id']:x for x in b['layers']};exits=read(O/'analysis-2023'/ref/'TOP10_WORST3_FIXED_PATHS.json')
    traces=[]
    for l in new:
        if l['sid'] not in selected:continue
        s=l['sid'];d=l['signal_day'];snap=dm[d];f=facts[s].loc[pd.Timestamp(d)];act=am[l['layer']]
        i=bydecision[s,d,l['role']];st=states[l['sector']][d]
        own=[x for x in snap['layers'] if x['sid']==s];closed=[x for x in b['layers'] if x['sid']==s and x['closed'] and x['closed'][:10]<=d]
        livecash=sum((n(x['cash'])+n(x['dividend']) for x in own),Z);pastcash=sum((n(x['cash'])+n(x['dividend']) for x in closed),Z)
        mark=sum((D(x['qty'])*n(f.raw_close) for x in own),Z);floor=Z;floorrows=[]
        for x in own:
            adj=x.get('last_core_line') if x['role']=='core' else x['floor']
            if adj is None:raise AssertionError(('unknown actual core protection',s,d,x['id']))
            raw=n(adj)/n(f.factor);floor+=D(x['qty'])*raw
            floorrows.append(dict(layer=x['id'],role=x['role'],pool=x['pool'],qty=x['qty'],actual_known_adjusted_line=adj,
                 current_factor=str(f.factor),raw_line=raw,buy_unit_gross_cost=x['unit_cost']))
        # Lifetime PnL includes prior closed failures and all known fees/dividends;
        # it is a valuation at stated lines, never executable guaranteed proceeds.
        traces.append(dict(reference=ref,sid=s,name=l['name'],layer=l['layer'],actual_open=l['opened'],signal_day=d,
            action=act['action'],actual_qty=act['quantity'],actual_gross=act['gross'],actual_fees=act['fees'],role=l['role'],pool=l['pool_at_fill'],
            I_valid=bool(f.i_target),I_new_buy=bool(f.i_buy),I_floor=str(f.i_floor),E0_valid=bool(f.e0_target),E0_floor=str(f.e0_floor),
            G1_ready=bool(f.g_ready),G1_grade=str(f.g_grade),G1_fresh_up=bool(f.g_fresh_up),G1_acute_down=bool(f.g_acute_down),
            adjusted_close=str(f.close),raw_close=str(f.raw_close),PVR_score=str(pvr[s].loc[pd.Timestamp(d),'score']),
            original_H1_score=i['score'],original_H1_rank=i.get('original_H1_rank',i['rank']),frozen_PVR_priority=i.get('priority_rank'),
            fresh_CP1_id=l['receipt'],frozen_protection_of_actual_role=i['floor'],
            industry_market_stage=st['stage_name'],industry_E0=st['E0_valid'],industry_close=st['close'],industry_mobile=st['mobile_after'],
            financial_attempt=l['attempt'],market_attempt=st['attempt_id'],ACT_on=snap['on'],
            own_roles_at_authorization=floorrows,prior_live_stock_economic_mark=livecash+mark,
            prior_live_stock_floor_value_net=livecash+floor,
            stock_lifetime_net_including_realized_and_fees_at_mark=pastcash+livecash+mark,
            stock_lifetime_net_including_realized_and_fees_at_known_lines=pastcash+livecash+floor,
            floor_value_excludes_future_sell_fees_and_gap_slippage=True,
            authorization_NAV=snap['nav'],prior_close_cash=snap['available'],prior_close_probe=snap['pool_probe'],prior_close_confirmed=snap['pool_confirmed'],
            exact_preopen_resource_owners='not saved at every decision; prior-close view is not exact opening state',
            final_new_layer_net=l['net'],actual_exit=l['closed']))
    save(Path(ref)/'ACTUAL_CASE_ENTRY_DECISIONS.json',traces)
    factsources={str(Path(A.SM[s]['refs']['facts'])):C.sha(A.SM[s]['refs']['facts']) for s in selected}
    save(Path(ref)/'CASE_SOURCE_HASHES.json',factsources)
    return groups,traces

def main():
    new=read(O/'analysis-2023/PVR_SLOT1/LAYERS_NEW2023.json');loss=collections.defaultdict(lambda:Z)
    for x in new:
        if not x['qty'] and n(x['net'])<0:loss[x['sid']]+=n(x['net'])
    worst=sorted(loss,key=lambda s:(loss[s],s))[0];assert worst=='600105.SH'
    ids=[worst,'601595.SH','300502.SZ']
    for ref,root in [('SC',W/'recovery-2023-readiness-20261101/runs/Bdiag'),('PVR_SLOT1',O/'run-2023')]:review(ref,root,ids)
    save('COMPLETION.json',dict(passed=True,account_replays=0,new_features=0,deterministic_worst_by_gross_closed_negative_stock=worst,
        selection_rule='all2023new layers; sum negative closed net bystock; ascending then code tie',
        cases=ids,first_wrong_entry_label='posthoc first funded decision in selected failed episode, never an asof-known wrong signal',
        data_scope='asof signal-close facts/actual frozen intents, actualfills, known lines; no unsaved exact preopen state reconstructed',
        source_sha256=C.sha(__file__)))
    print('CAUSAL2023_READONLY_DONE',ids,flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
