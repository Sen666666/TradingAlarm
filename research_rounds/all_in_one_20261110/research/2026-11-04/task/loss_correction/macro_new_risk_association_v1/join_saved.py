"""Bounded saved-JSON join only. No model, account, price loader or order writer."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,hashlib,datetime,collections
getcontext().prec=50
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');O=Path(__file__).resolve().parent
A=B/'ar6_native_feasibility/market_recovery_three_state';V=A/'structural_walk_daily_support_v2'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
def total(z,k):return None if any(k not in x or x[k] is None for x in z) else sum((D(str(x[k])) for x in z),D(0))
def agg(z):
    return dict(layers=len(z),stocks=len({x['sid'] for x in z}),known=sum(x['macrostate_asof'] in ['D','P','C'] for x in z),NA=sum(x['macrostate_asof'] not in ['D','P','C'] for x in z),cost=total(z,'cost'),net=total(z,'net'),positive_net=sum((D(x['net']) for x in z if D(x['net'])>0),D(0)),negative_net=sum((D(x['net']) for x in z if D(x['net'])<0),D(0)),positive_layers=sum(D(x['net'])>0 for x in z),negative_layers=sum(D(x['net'])<0 for x in z),open_layers=sum(int(x.get('qty',0))>0 for x in z),strict_realized=total(z,'strict_realized'),open_unrealized=total(z,'open_unrealized'),recognized_dividend_AR=total(z,'recognized_dividend_AR'),buy_fee=total(z,'buy_fee'),sell_fee=total(z,'sell_fee'))
def grouped(z):return {s:agg([x for x in z if x['macrostate_asof']==s]) for s in ['D','P','C','UNKNOWN']}
paths={w:B/f'risk_constraints/ma63_information_diagnostic_v1/{w}_ENTRIES.json' for w in ['2022_2024','strong']}
tailpath=B/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json'
rights_path=A/'market_new_risk_only/DAILY.json'
assert rights_path.exists(),'ar6 risk-only labels not yet ready; no fallback guessed labels'
daily=read(V/'DAILY.json');v2={r['day']:r for r in daily};rights_rows=read(rights_path);rights={r['day']:r for r in rights_rows}
assert len(v2)==len(daily)==len(rights)==len(rights_rows)==3273
acts={'2022_2024':{r['day']:r['ACT_after_CLOSE'] for r in read(B/'risk_constraints/continuation2024_finance/PVR_NO_CONFIRMED60_DAILY.json')},'strong':{r['day']:r['ACT_after_CLOSE'] for r in read(B/'risk_constraints/absolute_loss_2022_2023/NO60_STRONG_DAILY.json')}}
src=[*paths.values(),tailpath,V/'DAILY.json',V/'WINDOWS.json',rights_path,O/'PROTOCOL.txt',Path(__file__),B/'risk_constraints/continuation2024_finance/PVR_NO_CONFIRMED60_DAILY.json',B/'risk_constraints/absolute_loss_2022_2023/NO60_STRONG_DAILY.json']
save('INPUT_FREEZE.json',dict(before_join=True,frozen_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256={str(p):sha(p) for p in src},source='original saved v2 and ar6 rights labels, no recomputed macro',new_model_or_account_events=0))
def join(x,w,tail=False):
    x=dict(x);d=x['budget_order'].split('|')[1];assert d[:10]==x['decision_at'][:10] and d[11:19]=='15:10:00'
    day=d[:10];r=rights.get(day);v=v2.get(day);state=None if r is None else r['macrostate_after']
    assert state==(None if v is None else v['market_structural_state'])
    if r is not None:assert str(r['decision_close'])==d.replace('T',' ')
    x.update(macrostate_asof=state if state in ['D','P','C'] else 'UNKNOWN',macro_unknown_reason=None if state in ['D','P','C'] else 'no_known_state_at_exact_original_decision',macro_source_day=day,newrisk_label=None if r is None else r['new_risk_label'],original_ACT_after_CLOSE_context=None if tail else acts[w].get(day),macrostate_before=None if r is None else r['macrostate_before'],macro_event=None if v is None else v['event'],original_book_cutoff='2024-12-31' if w=='2022_2024' else '2026-06-30',all_money_original_cutoff_association=True)
    return x
rows={w:[join(x,w) for x in read(p)] for w,p in paths.items()}
tails={w:[join(x,w,True) for x in z] for w,z in read(tailpath)['members'].items()}
windows={'2022_2024':[('ALL','2022-01-01','2024-12-31'),('2022_2023','2022-01-01','2023-12-31'),('2022L01','2022-01-01','2022-04-26'),('2022L02','2022-04-27','2022-07-04'),('2022L03','2022-07-05','2022-10-31'),('2023Q2_AI','2023-04-01','2023-06-30'),('2023Jul_false','2023-07-01','2023-09-29'),('2024pre924','2024-01-01','2024-09-23'),('2024sixclose','2024-09-24','2024-10-08'),('2024post924','2024-10-09','2024-12-31')],'strong':[('ALL','2025-07-01','2026-06-30'),('2025Q3','2025-07-01','2025-09-30'),('2025Q4','2025-10-01','2025-12-31'),('2026Q1','2026-01-01','2026-03-31'),('2026Q2','2026-04-01','2026-06-30')]}
summary={};examples={}
for w,rs in rows.items():
    save(w+'_ROWS.json',rs);summary[w]={}
    for label,lo,hi in windows[w]:
        q=[x for x in rs if lo<=x['decision_at'][:10]<=hi];f=[x for x in rs if lo<=x['opened'][:10]<=hi]
        summary[w][label]={'lo':lo,'hi':hi,'decision_cohort_all':agg(q),'decision_cohort_by_state':grouped(q),'actual_fill_cohort_all':agg(f),'actual_fill_cohort_by_decision_state':grouped(f),'decision_role_state':{r:grouped([x for x in q if x['role']==r]) for r in ['core','mobile']},'decision_action_state':{a:grouped([x for x in q if x['action']==a]) for a in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']},'decision_pool_state':{p:grouped([x for x in q if x['pool_at_fill']==p]) for p in ['probe','confirmed']},'state_calendar_closes':dict(collections.Counter(r['macrostate_after'] or 'UNKNOWN' for r in rights_rows if lo<=r['day']<=hi)),'period_newlayer_wealth_computed':False}
    d=[x for x in rs if x['macrostate_asof']=='D'];examples[w]={'selection':'posthoc original top3 positive and negative D newlayers, no causal/policy claim','D_original_positive_top3':sorted([x for x in d if D(x['net'])>0],key=lambda x:D(x['net']),reverse=True)[:3],'D_original_negative_top3':sorted([x for x in d if D(x['net'])<0],key=lambda x:D(x['net']))[:3]}
post=[x for x in rows['2022_2024'] if '2024-10-08'<x['opened'][:10]<='2024-12-31'];assert len(post)==303
summary['2022_2024']['strict303_newfills']={'all':agg(post),'by_decision_state':grouped(post),'period_newlayer_wealth_computed':True,'period_wealth_equals_original_net_reason':'already audited saved Oct8 to Dec31 newfill-only bridge; no inventory before entry and common original book cutoff Dec31; not a macro-state period wealth path'}
fixed={w:{'all':agg(z),'by_state':grouped(z),'by_role_state':{r:grouped([x for x in z if x['role']==r]) for r in ['core','mobile']},'full_original_members':z,'claim_fee_splits_unknown_if_absent':True} for w,z in tails.items()}
save('SUMMARY.json',summary);save('FIXED_ORIGINAL_TAILS.json',fixed);save('D_SAME_STATE_EXAMPLES.json',examples)
for w,z in rows.items():assert len(z)=={'2022_2024':2265,'strong':1171}[w]
for w,z in tails.items():assert len(z)=={'2022_2024':83,'strong':94}[w]
for w,scopes in summary.items():
    for label,q in scopes.items():
        ss=q.get('decision_cohort_by_state',q.get('by_decision_state'));allq=q.get('decision_cohort_all',q.get('all'))
        assert sum(x['layers'] for x in ss.values())==allq['layers']
        assert abs(sum((D(x['net']) for x in ss.values()),D(0))-D(allq['net']))<D('1e-20')
save('COMPLETED.json',dict(status='PASS_SAVED_ASSOCIATION_ONLY',new_models=0,new_accounts=0,all_original_sources_unchanged=all(sha(p)==h for p,h in read(O/'INPUT_FREEZE.json')['source_sha256'].items()),layer_counts={w:len(x) for w,x in rows.items()},fixed_tail_counts={w:len(x) for w,x in tails.items()},not_candidate_PnL_NAV_or_avoidable_loss=True))
print(json.dumps({'by_state':{w:z['ALL']['decision_cohort_by_state'] for w,z in summary.items()},'strict303':summary['2022_2024']['strict303_newfills'],'fixed_tail_states':{w:z['by_state'] for w,z in fixed.items()},'output':str(O)},ensure_ascii=False,default=str,indent=2))
