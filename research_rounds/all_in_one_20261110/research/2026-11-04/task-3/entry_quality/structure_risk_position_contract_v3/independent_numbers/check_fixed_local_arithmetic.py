"""Five fixed original prefixes; independent Decimal fee/quantity arithmetic only."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import json, hashlib

OUT = Path(__file__).resolve().parent
V3 = OUT.parent
RULES = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
SRC = {}
Z = D(0)
def read(p):
    p=Path(p); b=p.read_bytes(); SRC[str(p)]=hashlib.sha256(b).hexdigest(); return json.loads(b)
inputs=read(OUT/'FIXED_ORIGINAL_PREFIX_INPUTS.json')['cases']
drows=read(OUT/'ACTUAL_PREFIX_D_ARITHMETIC.json')['rows']
dm={(r['sid'],r['decision_day']):r for r in drows}
rules=read(RULES)
card=V3/'designer/MINIMUM_MATH_CONTRACT.md'; SRC[str(card)]=hashlib.sha256(card.read_bytes()).hexdigest()

def fee(side, notional, q, schedule):
    # Independent scalar implementation of already read FeeSchedule; no ledger imports.
    if not q: return Z
    total=Z
    for c in schedule['components']:
        if c.get('side','both') not in ('both',side): continue
        assert c.get('amount_basis','notional')=='notional', 'Notional-only fixed dates in these cases'
        x=max(D(c.get('minimum_local','0')),notional*D(c['rate']))
        if c.get('maximum_local') is not None: x=min(x,D(c['maximum_local']))
        if c.get('rounding_unit') is not None:
            unit=D(c['rounding_unit']); x=(x/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
        total+=x
    return total

origin={(r['sid']):r for r in inputs if r['decision_day'] in ['2022-01-10','2026-04-21']}
rows=[]
for x in inputs:
    sid,day=x['sid'],x['decision_day']; p=D(x['actual_next_fill']['price']); fill_day=x['actual_next_fill']['at'][:10]
    venue='SSE_STAR' if sid=='688146.SH' else 'SZSE_MAIN'
    versions=[v for v in rules['fee_versions'][venue] if v['from']<=fill_day<v['to']]
    assert len(versions)==1; schedule=versions[0]['schedule']
    role='core' if x['actual_next_fill']['kind']=='core' else 'mobile'
    intent=next(i for i in x['original_intents'] if i['role']==role)
    h=D(intent['floor'])/D(str(x['original_facts']['factor']))
    B=D(origin[sid]['same_day_actual_account']['NAV'])*D('.0025')
    D_before=max(Z,D(dm[sid,day]['D_from_actual_prefix_if_same_k_is_proved']))
    existing=[]
    for l in x['existing_original_inventory']:
        t=l['saved_native_layer']; q=D(t['qty'])
        # Selected five prefixes have no partially sold live layer or split.
        K=q*D(str(t['unit_cost']))
        existing.append({'layer':l['layer'],'q':q,'gross_basis':K,'mark':D(str(x['original_facts']['raw_close'])),'line':D(l['guard_after_original_CLOSE_raw'])})
    def calc(q):
        group=list(existing)
        if q: group.append({'layer':'proposed','q':D(q),'gross_basis':D(q)*p,'mark':p,'line':h})
        for l in group: l=dict(l)
        qtotal=sum((l['q'] for l in group),Z)
        proceeds=[l['q']*min(l['mark'],l['line'])*D('.9995') for l in group]
        sellfee=fee('sell',sum(proceeds,Z),qtotal,schedule)
        layers=[]
        for l,proceed in zip(group,proceeds):
            allocated=sellfee*l['q']/qtotal if qtotal else Z
            kappa=max(Z,l['gross_basis']-proceed+allocated)
            giveback=max(Z,l['q']*l['mark']-proceed+allocated)
            layers.append({'layer':l['layer'],'q':str(l['q']),'gross_basis':str(l['gross_basis']),'plan_net_before_allocated_fee':str(proceed),'allocated_sellfee':str(allocated),'kappa':str(kappa),'marked_giveback':str(giveback)})
        buyfee=fee('buy',D(q)*p,D(q),schedule)
        kappa=sum((D(l['kappa'])for l in layers),Z)
        return {'q':q,'D_before':str(D_before),'buyfee_unpaid_or_newly_paid_once':str(buyfee),'prospective_same_sid_sellfee_once':str(sellfee),'kappa_sum_positive_per_layer':str(kappa),'local_total_D_plus_buyfee_plus_kappa':str(D_before+buyfee+kappa),'layers':layers}
    minimum,step=(200,1) if venue=='SSE_STAR' else (100,100)
    cap=int(intent['cap']); budget=D(intent['budget'])
    candidates=[q for q in range(minimum,cap+1,step) if D(q)*p<=budget]
    values=[(q,calc(q))for q in candidates]
    feasible=[(q,v)for q,v in values if D(v['local_total_D_plus_buyfee_plus_kappa'])<=B]
    qmax=max((q for q,_ in feasible),default=0)
    chosen=calc(qmax)
    nextlegal=qmax+step if qmax else minimum
    witnesses={'chosen':chosen,'next_legal_quantity':calc(nextlegal)}
    if sid=='688146.SH' and day=='2026-04-21':
        witnesses['reported_risk_only_495']=calc(495); witnesses['reported_risk_only_496']=calc(496)
    rows.append({'sid':sid,'decision_day':day,'original_next_OPEN':fill_day,'role':role,'source_intent':intent,'original_dated_venue':venue,'fee_schedule_id':schedule['schedule_id'],'B_origin_signal_NAV':origin[sid]['same_day_actual_account']['NAV'],'B_once':str(B),'D_before':str(D_before),'raw_known_buy_price':str(p),'raw_frozen_plan_line':str(h),'source_cap':cap,'source_frozen_gross_budget':str(budget),'local_q_after_original_source_cap_and_gross':qmax,'baseline_local_over_B':D(calc(0)['local_total_D_plus_buyfee_plus_kappa'])>B,'witnesses':witnesses,'quantity_scope':'LOCAL_B_D_KAPPA_PLUS_ORIGINAL_FROZEN_SOURCE_CAP_AND_GROSS_ONLY','not_checked':['Whole portfolio Omega/A and sector stress T','Legacy sector1/probe0.5 and all stock/pool/cash constraints','Causal capacity and physical sellable inventory','Full k canonical origin proof in this arithmetic file; separate source review required'],'final_grant':False})
result={'status':'FIVE_FIXED_LOCAL_ARITHMETIC_NOT_FINAL_GRANT','sellfee_grouping':'All same-sid nonpending prospective layer exits, including proposed layer, one fee order; differing plan lines affect total notional but not the minimum-fee order count. Fees allocated by raw shares; kappa positive part per layer.','rows':rows,'new_accounts':0,'new_models':0,'new_parameter_sweeps':0,'new_performance_path':0,'source_sha256':SRC}
result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT/'INDEPENDENT_FIVE_LOCAL_ARITHMETIC.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'sid':r['sid'],'day':r['decision_day'],'B':r['B_once'],'D':r['D_before'],'local_source_bounded_q':r['local_q_after_original_source_cap_and_gross'],'chosen_cost':r['witnesses']['chosen']['local_total_D_plus_buyfee_plus_kappa']}for r in rows],ensure_ascii=False))
