"""Both saved policies' strict H1 CP1 funnels. No runner/model imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,gzip,hashlib,importlib.util,time
import pandas as pd
P=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=W/'pvr-slot1-native-readiness-20261101'
ROOTS={'PVR_BASELINE':OLD/'runs/2025_26','PVR_NO60':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26')}
spec=importlib.util.spec_from_file_location('old_semiconductor_cache_reader',OLD/'semiconductor-2026H1-readonly/analyze_readonly.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
META,SM,IM=S.META,S.SM,S.IM
SEC='URFI881121';LO='2026-01-01';HI='2026-06-30';Z=D(0);SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SOURCES[str(p)]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
    SOURCES[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:
        for line in f:yield json.loads(line)
def book(p):
    SOURCES[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def save(name,x):
    with (P/name).open('x') as f:json.dump(S.clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def day(at):return str(at)[:10]
def n(x):return D(str(x))
def minimum(sid,d,snap):
    f=S.frame(sid);t=pd.Timestamp(d);assert t in f.index
    rr=f.loc[t];price=n(rr.raw_close);nav=n(snap['nav']);held=snap['positions'].get(sid,0)
    budget=min(nav*D('.02'),max(Z,nav*D('.1')-D(held)*price))
    versions=RULES['quantity_versions'].get(sid,[]);valid=[v for v in versions if v['from']<=d and (v['to'] is None or d<=v['to'])]
    assert len(valid)==1;v=valid[0];unit=v['rule']['buy_minimum'];gross=D(unit)*price
    reason='zero_remaining_stock_nominal_gap' if budget<=0 else 'positive_target_below_legal_initial_minimum' if budget<gross else 'unresolved_no_nominal_gap'
    return dict(normalized=reason,decision_close_price=price,decision_NAV=nav,actual_close_held_quantity=held,normal_fresh_target2pct=nav*D('.02'),remaining_stock10pct_gross=max(Z,nav*D('.1')-D(held)*price),actual_nominal_budget=budget,legal_minimum_quantity=unit,legal_minimum_gross_before_fees=gross,gross_shortfall=gross-budget,dated_rule=v['rule'],rule_source=v['source_id'],pre_intent_nominal_diagnosis_only=True)

def analyze(name,root,states):
    b=book(root/'pair/B.json.gz');daily=list(rows(root/'pair/daily.jsonl.gz'));dd={day(x['at']):x for x in daily};cal=list(dd);nxt={d:cal[i+1] for i,d in enumerate(cal[:-1])}
    op=[x for x in rows(root/'pair/opportunities.jsonl.gz') if x['sector']==SEC and LO<=x['day']<=HI]
    funding=[x for x in rows(root/'pair/funding.jsonl.gz') if LO<=day(x['at'])<=HI and META[x['sid']]['sector_id']==SEC]
    ci={};opening=defaultdict(list);closing=defaultdict(list)
    for d in b['decisions']:
        if not LO<=day(d['at'])<=HI:continue
        for i in d['intents']:
            if META[i['sid']]['sector_id']==SEC:
                key=(day(d['at']),i['sid'],i['role']);assert key not in ci;ci[key]=i
    for f in funding:(opening if '09:30:00' in f['at'] else closing)[day(f['at']),f['sid'],f['role']].append(f)
    bought={t['layer']:t for t in b['trades'] if t['side']=='buy'}
    jr={j['layer']:j for j in b['journal'] if j['kind']=='real_buy_fill'}
    filled={(j['sid'],day(j['signal_at']),j['CP1_id']) for j in jr.values() if j['role']=='mobile'}
    fr=[x for x in op if x['CP1_id']];q=[x for x in fr if x['mobile_Q'] is True]
    mother=[x for x in q if states.loc[x['day'],'stage_name'] in ('confirmed','expanded')]
    rr=[]
    for x in mother:
        d,sid=x['day'],x['sid'];i=ci.get((d,sid,'mobile'));cl=closing[d,sid,'mobile'];opn=opening[nxt[d],sid,'mobile'] if d in nxt else [];raw=[f['result'] for f in opn];norm=None
        if x['barriers']:cat='preplanning_account_barrier:'+','.join(x['barriers'])
        elif i is None:
            cat='not_planned_original_target_or_sizing'
            if any(f['result']=='no_nominal_gap' for f in cl):norm=minimum(sid,d,dd[d])
        elif d not in nxt:cat='terminal_close_next_open_outside_saved_account'
        elif any(z['result']=='reserved' for z in opn):cat='reserved_and_filled' if (sid,d,x['CP1_id']) in filled else 'reserved_zero_fill'
        elif opn:cat='opening_rejected_raw_merged_constraints'
        elif any(f['result']=='reserved' for f in opening[nxt[d],sid,'core']):cat='same_stock_core_reserved_suppresses_mobile'
        else:cat='no_mobile_opening_record_unknown_pending_or_skip'
        snap=dd[d]
        rr.append(dict(sid=sid,name=META[sid]['name'],signal_day=d,receipt=x['CP1_id'],market_stage=states.loc[d,'stage_name'],category=cat,raw_opening_reasons=raw,raw_close_reasons=[f['result'] for f in cl],normalized_no_plan=norm,opportunity=x,frozen_intent=i,next_saved_OPEN=nxt.get(d),actual_next_OPEN_records=opn,actual_any_mobile_fill_same_receipt=(sid,d,x['CP1_id']) in filled,observed_after_CLOSE_resources=dict(NAV=snap['nav'],available=snap['available'],inventory=snap['inventory'],order_reserved=snap['order_reserved'],probe_capital=snap['pool_probe'][0],probe_risk=snap['pool_probe'][1],confirmed_capital=snap['pool_confirmed'][0],confirmed_risk=snap['pool_confirmed'][1],held_stock_quantity=snap['positions'].get(sid,0),clock_scope='after signal-CLOSE; not pre-candidate OPEN; NO60 has no confirmed60 capacity limit')))
    accepted=[]
    for lid,t in bought.items():
        if META[t['security_id']]['sector_id']!=SEC or not LO<=day(t['at'])<=HI:continue
        j=jr[lid];sid=t['security_id'];signal=day(t['signal_at']);i=ci.get((signal,sid,j['role']));r=S.frame(sid).loc[pd.Timestamp(day(t['at']))];factor=n(r.factor);rawfloor=n(t['floor'])/factor
        exits=[e for e in b['audit'] if e['kind']=='pilot_layer_exit' and lid in e['layers']];sells=[q for q in b['trades'] if q['side']=='sell' and any(p['layer']==lid for p in q['parts'])];l=next(x for x in b['layers'] if x['id']==lid)
        accepted.append(dict(layer=lid,sid=sid,name=META[sid]['name'],signal_day=signal,receipt=j['CP1_id'],role=j['role'],pool_at_fill=j['pool'],actual_fill=t,frozen_signal_intent=i,entry_factor_known_corporate_action_units=factor,actual_initial_raw_floor=rawfloor,initial_nominal_price_to_floor_risk=D(t['shares'])*max(Z,n(t['price'])-rawfloor),floor_clock='frozen signal floor converted by entry-day corporate-action factor; no buy-day closing signal',exit_requests=exits,actual_sells=sells,terminal_layer=l))
    rejects=[x for x in rr if x['category']=='opening_rejected_raw_merged_constraints'];tags=Counter()
    for x in rejects:
        present=set()
        for raw in x['raw_opening_reasons']:present.update(raw.split(','))
        tags.update(present)
    summary=dict(policy=name,raw_CP1_receipts=len(fr),CP1_mobile_Q_true=len(q),confirmed_expanded_market_receipts=len(mother),unique_market_receipts=len({(x['sid'],x['day'],x['CP1_id']) for x in mother}),categories=dict(Counter(x['category'] for x in rr)),no_plan_normalized_counts=dict(Counter(x['normalized_no_plan']['normalized'] if x['normalized_no_plan'] else 'other_or_unknown' for x in rr if x['category']=='not_planned_original_target_or_sizing')),opening_reject_receipts=len(rejects),overlapping_raw_constraint_receipt_tags=dict(tags),raw_opening_reason_combinations=dict(Counter(raw for x in rejects for raw in x['raw_opening_reasons'])),actual_H1_all_role_layers=len(accepted),actual_H1_role_pool=dict(Counter(x['role']+'|'+x['pool_at_fill'] for x in accepted)),actual_mobile_receipts_in_mother=sum(x['actual_any_mobile_fill_same_receipt'] for x in rr),terminal_confirmed_market_receipts=sum(x['signal_day']==HI for x in rr),new_signals=0,new_accounts=0,no_counterfactual_relaxed_resource_claim=True)
    save(name+'-SEMICONDUCTOR_FUNNEL.json',dict(summary=summary,all_market_receipts=rr));save(name+'-SEMICONDUCTOR_ACCEPTED_LIFECYCLES.json',accepted)
    return rr,summary,{(x['sid'],x['day'],x['CP1_id']) for x in mother}

def main():
    global RULES
    start=time.monotonic();RULES=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
    meta=IM[SEC];p=Path(meta['refs']['state']);assert sha(p)==meta['output_sha256'][str(p)];SOURCES[str(p)]=sha(p);states=pd.read_parquet(p).set_index('day')
    allrows={};summ={};keys={}
    for name,root in ROOTS.items():allrows[name],summ[name],keys[name]=analyze(name,root,states)
    old,new=keys['PVR_BASELINE'],keys['PVR_NO60'];comparison=dict(side_summaries=summ,canonical_market_key_sets=dict(common=len(old&new),old_only=sorted(old-new),NO60_only=sorted(new-old),same_fixed_market_mother=old==new),not_independent_samples=True,policy_act_and_old_book_state_separately_observed=True,old833_not_copied_into_new=True)
    save('FUNNEL_COMPARISON.json',comparison)
    source=dict(SOURCES);source.update(S.SRC);source[str(Path(__file__))]=sha(__file__)
    save('FUNNEL_SOURCE_BINDING.json',dict(sources=source,seconds=time.monotonic()-start,zero_account_imports=True,financial_events=0,signals_recomputed=0))
    print(json.dumps(comparison,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
