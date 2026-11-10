"""One read-only grouping of existing funded layers and fixed original tails; no models/accounts."""
from pathlib import Path
from decimal import Decimal as D, getcontext
import json, collections, hashlib, datetime
import pandas as pd
getcontext().prec=50
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def read(p):return json.loads(Path(p).read_text())
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def agg(rows):
    # Fixed old-tail list has cost/net but not every accounting split: missing is NA, never zero.
    total=lambda k:None if any(k not in x or x[k] is None for x in rows) else sum((D(str(x[k])) for x in rows),D(0))
    return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),original_cost=total('cost'),original_net=total('net'),original_positive_net=sum((D(x['net']) for x in rows if D(x['net'])>0),D(0)),original_negative_net=sum((D(x['net']) for x in rows if D(x['net'])<0),D(0)),negative_layers=sum(D(x['net'])<0 for x in rows),positive_layers=sum(D(x['net'])>0 for x in rows),open_layers=sum(int(x.get('qty',0))>0 for x in rows),strict_realized=total('strict_realized'),open_unrealized=total('open_unrealized'),recognized_dividend_AR=total('recognized_dividend_AR'),buy_fee=total('buy_fee'),sell_fee=total('sell_fee'),g_ready_false=sum(x.get('current_g_ready') is False for x in rows))
sm_path=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';sm={x['symbol']:x for x in read(sm_path)}
previous=read(B/'loss_correction/volume_neutral_interpretation_v1/NATIVE_ENTRY_SEMANTICS_AUDIT.json')
allowed=previous['facts_source_sha256'];frames={};sources={};unknown=[]
paths={w:B/f'risk_constraints/ma63_information_diagnostic_v1/{w}_ENTRIES.json' for w in ['2022_2024','strong']}
tp=B/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json'
legs=read(B/'pvr_pool_feasibility/market_phase_2022_2023/HS300_ALL_LEGS.json')
if not (O/'SCOPE.json').exists():
    save('SCOPE.json',dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),question='new mobile capital current original G1 grade>=2 only; holding/core/exits unchanged; conditional association only',threshold='existing G1 WARM boundary 2; no search',original_mothers={str(p):sha(p) for p in list(paths.values())+[tp]},facts_scope='only prior1205 SHA-checked original facts, no new features',phase_clock='primary actual decision CLOSE membership for L03/L04; actual fill membership separately; strict303 actual fills after Oct8CLOSE',prohibited=['new model','new account','new neutral exports','deleted-PnL or new NAV','sizing changes','faster exit'],hard_scope_minutes=10))
def enrich(x,window):
    x=dict(x);sid=x['sid'];p=str(Path(sm[sid]['refs']['facts']));day=pd.Timestamp(x['decision_at'][:10]);reason=None
    if p not in allowed:reason='outside_previous1205_facts_scope'
    elif sid not in frames:
        assert sha(p)==allowed[p],('changed original facts',sid)
        frames[sid]=pd.read_parquet(p,columns=['g_grade','g_ready','i_target','i_buy','segment_id'])
        sources[p]=allowed[p]
    if reason is None and day not in frames[sid].index:reason='no_exact_decision_observation'
    if reason:
        x.update(grade_class='unknown',grade_unknown=reason,current_g_grade=None,current_g_ready=None);unknown.append([window,x['layer'],sid,reason]);return x
    q=frames[sid].loc[day];g=q.g_grade
    x.update(current_g_grade=None if pd.isna(g) else float(g),current_g_ready=None if pd.isna(q.g_ready) else bool(q.g_ready),original_I_target=None if pd.isna(q.i_target) else bool(q.i_target),original_I_buy=None if pd.isna(q.i_buy) else bool(q.i_buy),source_segment=float(q.segment_id),grade_class='unknown' if pd.isna(g) else 'grade_lt2' if float(g)<2 else 'grade_ge2',grade_unknown='grade_NA' if pd.isna(g) else None)
    return x
allrows={w:[enrich(x,w) for x in read(p)] for w,p in paths.items()}
tails={w:[enrich(x,'original_tail_'+w) for x in rows] for w,rows in read(tp)['members'].items()}
summary={}
for window,rows in allrows.items():
    scopes={'ALL':rows}
    if window=='2022_2024':
        scopes['2022_2023']=[x for x in rows if x['opened'][:10]<='2023-12-29']
        for leg in legs:
            if leg['id'] in ['L03','L04']:
                lo,hi=leg['first_analysis_day'],leg['last_analysis_day']
                scopes[leg['id']+'_decision_cohort']=[x for x in rows if lo<=x['decision_at'][:10]<=hi]
                scopes[leg['id']+'_actual_fill_cohort']=[x for x in rows if lo<=x['opened'][:10]<=hi]
        scopes['strict303_postOct8_newfills']=[x for x in rows if '2024-10-08'<x['opened'][:10]<='2024-12-31']
        assert len(scopes['strict303_postOct8_newfills'])==303
    summary[window]={}
    for name,z in scopes.items():
        item={'all':agg(z),'by_role_and_current_grade':{},'mobile_by_action_and_current_grade':{},'mobile_by_fillpool_and_current_grade':{}}
        for role in ['core','mobile']:
            item['by_role_and_current_grade'][role]={g:agg([x for x in z if x['role']==role and x['grade_class']==g]) for g in ['grade_lt2','grade_ge2','unknown']}
        for action in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']:
            item['mobile_by_action_and_current_grade'][action]={g:agg([x for x in z if x['role']=='mobile' and x['action']==action and x['grade_class']==g]) for g in ['grade_lt2','grade_ge2','unknown']}
        for pool in ['probe','confirmed']:
            item['mobile_by_fillpool_and_current_grade'][pool]={g:agg([x for x in z if x['role']=='mobile' and x['pool_at_fill']==pool and x['grade_class']==g]) for g in ['grade_lt2','grade_ge2','unknown']}
        summary[window][name]=item
    save(window+'_ROWS.json',rows)
fixed={w:{'all':agg(z),'by_role_and_grade':{r:{g:agg([x for x in z if x['role']==r and x['grade_class']==g]) for g in ['grade_lt2','grade_ge2','unknown']} for r in ['core','mobile']},'full_original_rows':z,'money_is_original_fixed_tail_not_new_policy_profit':True} for w,z in tails.items()}
save('SUMMARY.json',summary);save('FIXED_ORIGINAL_TAILS.json',fixed)
save('SOURCES_AND_LIMITS.json',dict(facts_sources=sources,unknown=unknown,new_model_events=0,new_account_events=0,new_neutral_features=0,script_sha256=sha(Path(__file__)),source_columns=['g_grade','g_ready','i_target','i_buy','segment_id'],labels='all lifecycle net/cost original; entry phase cohorts not phase wealth; fixed tails include marked/open/dividend contribution; no avoided loss/new return interpretation'))
print(json.dumps({'summary':{w:{scope:{r:v['by_role_and_current_grade'][r] for r in ['core','mobile']} for scope,v in scopes.items() if scope in ['ALL','2022_2023','L03_decision_cohort','L04_decision_cohort','strict303_postOct8_newfills']} for w,scopes in summary.items()},'fixed_tail':{w:z['by_role_and_grade'] for w,z in fixed.items()},'unknown':unknown,'output':str(O)},ensure_ascii=False,default=str,indent=2))
