"""Read-only saved-source arithmetic. No strategy/model/account imports."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import Counter, defaultdict
import json, hashlib, gzip
import pandas as pd
getcontext().prec = 50
B = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
O = B/'independent_review/market_recovery_three_state_review'
A = B/'ar6_native_feasibility/market_recovery_three_state'
L = B/'loss_correction/macro_new_risk_association_v1'
R = B/'risk_constraints/market_regime_risk/natural_exit_v2'
Z = D(0)
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def close(a,b): assert abs(D(str(a))-D(str(b))) < D('1e-8'), (a,b)
def save(n,x):
    p=O/n; assert not p.exists(),p
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
    return str(p),sha(p)
sources={}
def bind(p): sources[str(p)]=sha(p)
def check_map(m):
    for p,h in m.items():
        assert sha(p)==h,p
        sources[p]=h
rights_dir=A/'market_new_risk_only'
check_map(read(rights_dir/'SOURCE_FREEZE.json'))
check_map(read(L/'INPUT_FREEZE.json')['source_sha256'])
check_map(read(R/'SOURCE_MANIFEST.json'))
v2=read(A/'structural_walk_daily_support_v2/DAILY.json')
rights=read(rights_dir/'DAILY.json'); assert len(rights)==len(v2)==3273
cal=pd.read_csv('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv',usecols=['date']).date.tolist()
assert [x['day'] for x in rights]==cal
byday={r['day']:r for r in rights}
for i,(raw,r) in enumerate(zip(v2,rights)):
    assert all(r[k]==v for k,v in raw.items()),r['day']
    state=raw['market_structural_state']; category={None:'NA_NO_MARKET_STATE','D':'ZERO_NEW_OPEN_ADD','P':'PROBE_CATEGORY_UNSIZED','C':'CONDITIONAL_INCREMENT_CATEGORY_UNSIZED'}[state]
    assert r['decision_close']==raw['at']==r['asof'] and r['macrostate_after']==state
    assert r['new_risk_label']==r['macro_new_risk_category']==category
    assert r['macro_zero_new_risk_permission'] is (True if state=='D' else None)
    assert r['macro_P_C_cap_or_executable_permission'] is None
    nxt=cal[i+1] if i+1<len(cal) else None
    assert r['next_market_date']==nxt
    assert r['next_market_planned_OPEN']==(None if nxt is None else nxt+' 09:30:00+08:00')
    assert r['next_OPEN_endpoint_censored']==(nxt is None)
    assert not r['pending_fills_are_assumed_zero'] and not r['floating_profit_loss_used']
    assert r['old_inventory_macro_action']=='NO_MACRO_FORCED_SELL_USE_ORIGINAL_I_CP1_EXIT'
    assert r['cancel_unfilled_buy_intents_asof_CLOSE']==('REQUEST_CANCEL_AWAIT_ACK' if state=='D' else 'NO_MACRO_D_CANCEL_REQUEST')
    old=raw['old_ACT_context']; assert r['historical_H_context_only']==(None if old is None else not bool(old['on']))
    assert r['historical_ACT_not_new_path'] and r['all_roles_same_macro_label']

fields=['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']
def agg(rs):
    a=dict(layers=len(rs),stocks=len({r['sid']for r in rs}),known=sum(r['macrostate_asof']in['D','P','C']for r in rs),NA=sum(r['macrostate_asof']not in['D','P','C']for r in rs),positive_layers=sum(D(r['net'])>0 for r in rs),negative_layers=sum(D(r['net'])<0 for r in rs),open_layers=sum(int(r.get('qty',0))>0 for r in rs))
    for k in fields: a[k]=None if any(r.get(k) is None for r in rs) else sum((D(str(r[k]))for r in rs),Z)
    a['positive_net']=sum((D(r['net'])for r in rs if D(r['net'])>0),Z)
    a['negative_net']=sum((D(r['net'])for r in rs if D(r['net'])<0),Z)
    return a
def verify(a,b):
    for k,x in a.items():
        if x is None: assert b[k] is None,(k,b[k])
        elif isinstance(x,D): close(x,b[k])
        else: assert x==b[k],(k,x,b[k])
def grouped(rs): return {s:agg([r for r in rs if r['macrostate_asof']==s])for s in ['D','P','C','UNKNOWN']}
summary=read(L/'SUMMARY.json'); tails=read(L/'FIXED_ORIGINAL_TAILS.json')
orig_tail=read(B/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
key={}; checked_groups=0
for w,n in [('2022_2024',2265),('strong',1171)]:
    original=read(B/f'risk_constraints/ma63_information_diagnostic_v1/{w}_ENTRIES.json')
    rs=read(L/(w+'_ROWS.json')); assert len(rs)==len(original)==n
    assert len({r['layer']for r in rs})==n
    for r,q in zip(rs,original):
        assert all(r[k]==v for k,v in q.items()),(w,r['layer'])
        dec=r['budget_order'].split('|')[1].replace('T',' '); assert dec==r['decision_at']
        m=byday[dec[:10]]; assert dec==m['decision_close'] and dec[11:19]=='15:10:00'
        assert r['macrostate_asof']==m['macrostate_after'] and r['newrisk_label']==m['new_risk_label']
        assert r['opened']>dec and r['opened'][11:19]=='09:30:00'
        close(D(r['strict_realized'])+D(r['open_unrealized'])+D(r['recognized_dividend_AR']),r['net'])
    for label,q in summary[w].items():
        if label=='strict303_newfills':
            chosen=[r for r in rs if '2024-10-08'<r['opened'][:10]<='2024-12-31']
            assert len(chosen)==303 and {r['macrostate_asof']for r in chosen}=={'C'}
            verify(agg(chosen),q['all'])
            for s,a in grouped(chosen).items():verify(a,q['by_decision_state'][s]);checked_groups+=1
            continue
        chosen=[r for r in rs if q['lo']<=r['decision_at'][:10]<=q['hi']]
        fill=[r for r in rs if q['lo']<=r['opened'][:10]<=q['hi']]
        verify(agg(chosen),q['decision_cohort_all']);verify(agg(fill),q['actual_fill_cohort_all'])
        for s,a in grouped(chosen).items():verify(a,q['decision_cohort_by_state'][s]);checked_groups+=1
        for s,a in grouped(fill).items():verify(a,q['actual_fill_cohort_by_decision_state'][s]);checked_groups+=1
        for field,subkey in [('role','decision_role_state'),('action','decision_action_state'),('pool_at_fill','decision_pool_state')]:
            for value,stored in q[subkey].items():
                for s,a in grouped([r for r in chosen if r[field]==value]).items():verify(a,stored[s]);checked_groups+=1
        assert Counter(r['macrostate_after']or'UNKNOWN'for r in rights if q['lo']<=r['day']<=q['hi'])==Counter(q['state_calendar_closes'])
        assert not q['period_newlayer_wealth_computed']
    ts=tails[w]['full_original_members'];assert len(ts)==len(orig_tail[w])=={'2022_2024':83,'strong':94}[w]
    for r,q in zip(ts,orig_tail[w]):
        assert all(r[k]==v for k,v in q.items())
        assert r['macrostate_asof']==byday[r['decision_at'][:10]]['macrostate_after']
    verify(agg(ts),tails[w]['all'])
    for s,a in grouped(ts).items():verify(a,tails[w]['by_state'][s]);checked_groups+=1
    key[w]={'all':grouped(rs),'fixed_original_tails':grouped(ts)}
key['strict303']=summary['2022_2024']['strict303_newfills']
for p in [L/'SUMMARY.json',L/'FIXED_ORIGINAL_TAILS.json',L/'2022_2024_ROWS.json',L/'strong_ROWS.json',rights_dir/'DAILY.json',rights_dir/'RESULTS.json',B/'pvr_pool_feasibility/market_new_risk_only/RIGHTS_PRIORITY_TRANSITIONS.txt']:bind(p)

# Original fixed-layer depletion: raw quotes only, no account/cash-basis reconstruction.
sm=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');sm={r['symbol']:r for r in sm};prices={}
def raw(sid,day):
    if sid not in prices:
        p=Path(sm[sid]['refs']['facts']);assert sha(p)==sm[sid]['output_sha256'][str(p)]
        prices[sid]=pd.read_parquet(p,columns=['raw_close'])
    return D(str(prices[sid].loc[:day].raw_close.iloc[-1]))
refs={'two_year':(B/'pvr_pool_feasibility/continuation2023/run-2023/pair/B.json.gz',[B/'risk_constraints/pvr_pool_results_2022/PVR_NO_CONFIRMED60_DAILY.json',B/'risk_constraints/no60_continuation2023_finance/PVR_NO_CONFIRMED60_2023_DAILY.json']), 'strong':(B/'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz',[B/'risk_constraints/pvr_pool_results_2025_26/PVR_NO_CONFIRMED60_DAILY.json'])}
cases=read(R/'ALL_CASES.json'); flows=read(R/'INITIAL_LAYER_SELL_PARTS.json')
expected_events={(w,r['day'])for w,(bp,dps)in refs.items()for r in v2 if r['event']=='support_break_D' and r['day'] in {str(x['at'])[:10]for p in dps for x in read(p)}}
assert {(c['window'],c['D_day'])for c in cases if c['case_kind']=='v2_support_break_D'}==expected_events
assert len(cases)==12 and len(expected_events)==11
native={}; checked_parts=0
for w,(bp,dps)in refs.items():
    with gzip.open(bp,'rt')as f:book=json.load(f)
    snaps={str(x['at'])[:10]:x for p in dps for x in read(p)}
    native[w]=(book,snaps)
for c in cases:
    w,day,end=c['window'],c['D_day'],c['end']; book,snaps=native[w]; a,z=snaps[day],snaps[end]
    initial={x['id']:x for x in a['layers']if D(x['qty'])>0}; ending={x['id']:x for x in z['layers']if D(x['qty'])>0}
    assert len(initial)==c['initial_layers'];close(sum((D(l['qty'])*raw(l['sid'],day)for l in initial.values()),Z),c['initial_original_inventory'])
    assert c['initial_stocks']==len(a['positions']) and c['initial_pending_original_exits']==len(a['pending_sells'])
    splits=[x for x in book['audit']if x['kind']=='split']
    def ratio(sid,at):
        k=D(1)
        for x in splits:
            if x['sid']==sid and day+' 15:10:00+08:00'<str(x['at'])<=at:k*=D(x['ratio'])
        return k
    def cat(reason):
        if reason=='I_structure_exit':return'I_structure'
        if reason=='CP1_add_protection':return'CP1_structure'
        if reason=='ACT_pause':return'old_ACT20_force'
        if 'fund' in str(reason).lower()or'筹资'in str(reason):return'funding_sale'
        return'other'
    selected=[f for f in flows if f['window']==w and f['D_day']==day]
    expected=[];sold=defaultdict(lambda:Z);groups=defaultdict(list);allgroups=defaultdict(list)
    for t in book['trades']:
        if t['side']!='sell'or not(day<str(t['at'])[:10]<=end):continue
        for p in t['parts']:
            k=cat(p.get('reason',t.get('reason')));allgroups[k].append(p)
            if p['layer']not in initial:continue
            l=initial[p['layer']];q=D(p['shares'])/ratio(l['sid'],t['at']);sold[p['layer']]+=q
            expected.append((p['layer'],l['sid'],t['at'],k,D(p['shares']),q,q*raw(l['sid'],day),D(p['net_cash'])))
    got=[(f['layer'],f['sid'],f['fill_at'],f['category'],D(f['actual_shares']),D(f['D_equivalent_shares']),D(f['D_mark_equivalent']),D(f['actual_net_sale_cash']))for f in selected]
    assert got==expected,(w,day,'native selected sell parts');checked_parts+=len(got)
    for f in expected:groups[f[3]].append(f)
    for k,g in c['original_exit_groups'].items():
        fs=groups[k];assert len(fs)==g['sell_parts']and len({f[0]for f in fs})==g['distinct_layers']
        close(sum((f[6]for f in fs),Z),g['D_mark_equivalent_shares_sold']);close(sum((f[7]for f in fs),Z),g['actual_net_sale_cash'])
        ag=c['all_original_exits_including_later_buys'][k]; ps=allgroups[k]
        assert len(ps)==ag['sell_parts']and sum(p['layer']in initial for p in ps)==ag['initial_cohort_parts']
        close(sum((D(p['net_cash'])for p in ps),Z),ag['actual_net_sale_cash'])
    remainD=Z;remainmark=Z
    for i,l in initial.items():
        q=D(ending.get(i,{}).get('qty',0));eq=q/ratio(l['sid'],end+' 15:10:00+08:00')
        close(D(l['qty']),sold[i]+eq);remainD+=eq*raw(l['sid'],day);remainmark+=q*raw(l['sid'],end)
    close(remainD,c['initial_cohort_remaining_D_mark_equivalent']);close(remainmark,c['initial_cohort_remaining_actual_end_marketvalue'])
    newmark=sum((D(l['qty'])*raw(l['sid'],end)for i,l in ending.items()if i not in initial),Z)
    close(newmark,c['new_original_layers_actual_end_marketvalue']);close(remainmark+newmark,c['original_end_total_inventory'])
    buys=[t for t in book['trades']if t['side']=='buy'and day<str(t['at'])[:10]<=end]
    assert len(buys)==c['original_following_new_buy_fills'];assert all(t['layer']not in initial for t in buys)
    close(sum((D(t['gross_cny'])+D(t['fees_cny'])for t in buys),Z),c['original_following_new_layer_buy_cash'])
for p in [R/'ALL_CASES.json',R/'INITIAL_LAYER_SELL_PARTS.json',R/'COMPLETED.json']:bind(p)
out={'status':'PASS_WITH_SCOPE_SAVED_LABELS_AND_ORIGINAL_PATH_ASSOCIATIONS;NO_FINANCIAL_ADMISSION',
     'rights_label_rows_checked':3273,'mother_layers_checked':{'2022_2024':2265,'strong':1171},'fixed_original_tail_records_checked':{'2022_2024':83,'strong':94},'aggregate_groups_recomputed':checked_groups,
     'original_D_cohort_cases_checked':12,'original_D_cohort_sell_parts_native_checked':checked_parts,
     'key_original_associations':key,
     'original_exit_cases':[{k:c[k]for k in ['window','D_day','end','initial_original_inventory','initial_layers','original_exit_groups','share_depletion_milestones','original_following_new_layer_buy_cash','initial_cohort_remaining_actual_end_marketvalue','new_original_layers_actual_end_marketvalue']}for c in cases],
     'verdict':'Do not promote whole-market new-risk gate or build C funding feedback. Strict303 loss is entirely original C; strong original D contains substantial positive and negative contributions and33fixedtail records. Associations do not prove any veto policy profitability. Shift hypothesis toward sector/stock dynamic risk under parent scope.',
     'paper_scope':['D cancels new OPEN/ADD only, ACK resources retained; no macro forced old sells or PnL based sell exceptions','P single incremental10%gross/.5%nominal legacy reference, old constraints counted; exact authorization consumption/refund/NAV/fees undefined','C rights and amount BLOCKED; needs actual same post-P/post-H trial IDs and effective original protection feedback; no floating profit or migration proxy','H only abstract candidate-own ACT20 contract, no new H/flat/recovery path computed; old ACT sidecar does not authorize P/C','NextOPEN is market planned calendar only; not stock execution; finalendpoint unknown'],
     'limits':['All money except strict303 is original entry-cohort contribution at common final cutoff, not within-state/phase wealth or avoidable loss','Strict303 uses already audited original Oct8-Dec31 newfill bridge; no hypothetical capital reallocation','12cohorts can overlap; D-mark-equivalent is split-normalized share depletion at original D mark, not sale cash, nominal-risk release or new NAV','Original I/CP1, funding and ACT fill timing is historical only. New buying veto changes subsequent state/resources and must not inherit those exits','No new model/state walk/account/risk book created; no new economics/implementation authority','Natural-exit milestone dates source-reviewed, sale selection/quantity/money and endpoint bridges independently checked; not separate full strategy replay'],
     'source_sha256':sources}
p,h=save('MARKET_NEW_RISK_ONLY_AUDIT.json',out)
print(json.dumps({'audit':p,'sha256':h,'groups':checked_groups,'native_parts':checked_parts,'status':out['status'],'key':{w:{s:{k:a[k]for k in ['layers','cost','net','positive_net','negative_net']}for s,a in key[w]['all'].items()}for w in ['2022_2024','strong']}},ensure_ascii=False,default=str))
