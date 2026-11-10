"""Written-contract arithmetic only. No policy, route, preview, request or account.
Manually stipulated valid-stage/fresh-mobile orders check conservation and caps.
"""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib,copy
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'case-stage-ledger-20261031/v3'))
import joint_v3 as J
Z=D(0);NAV=D(1000000)
rulespath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
rules=json.loads(rulespath.read_text());sd=next(r['schedule'] for r in rules['fee_versions']['SZSE_MAIN'] if r['from']<='2023-01-20' and (not r.get('to') or '2023-01-20'<r['to']))
schedule=J.LR.L.FeeSchedule(sd['schedule_id'],tuple(J.LR.L.FeeComponent(**x) for x in sd['components']))
def fee(q,p):return J.LR.fees(q,D(p),schedule,'buy',D(1))
def row(sid,sector,pool,role,qty,mark,floor,*,pending=False,status='held',attempt='current'):
    return dict(stock=sid,sector=sector,pool=pool,role=role,qty=qty,mark=D(mark),floor=D(floor),pending=pending,status=status,attempt=attempt,fee=fee(qty,mark) if pending else Z)
def resources(rows,pool=None,sector=None):
    a=[r for r in rows if (pool is None or r['pool']==pool) and (sector is None or r['sector']==sector)]
    return dict(capital=sum((r['qty']*r['mark'] for r in a),Z),risk=sum((r['qty']*max(Z,r['mark']-r['floor']) for r in a),Z),reserve=sum((r['qty']*r['mark']+r['fee'] for r in a if r['pending']),Z))
def check(rows,cash,stage_cap='0.10'):
    fees=sum((r['fee'] for r in rows if r['pending']),Z);bn=NAV-fees;a=resources(rows);pr=resources(rows,'probe');cf=resources(rows,'confirmed');s=resources(rows,sector='S')
    flags=dict(probe_capital=pr['capital']<=D('.10')*bn,probe_risk=pr['risk']<=D('.005')*bn,confirmed_capital=cf['capital']<=D('.60')*bn,sector_S_capital=s['capital']<=D(stage_cap)*bn,sector_S_risk=s['risk']<=D('.01')*bn,account_three_percent_if_enabled=a['risk']<=D('.03')*bn,cash_and_original_reserve=cash-a['reserve']>=D('.10')*NAV,
               per_stock_ten_percent=all(sum((x['qty']*x['mark'] for x in rows if x['stock']==sid),Z)<=D('.10')*NAV for sid in {r['stock'] for r in rows}),
               other_industries_ten_percent=all(resources(rows,sector=g)['capital']<=D('.10')*bn and resources(rows,sector=g)['risk']<=D('.01')*bn for g in {r['sector'] for r in rows}-{'S'}))
    return dict(total=a,probe=pr,confirmed=cf,sector_S=s,pending_fees=fees,budget_NAV=bn,available_after_reserves=cash-a['reserve'],checks=flags)

# Example 1: S already confirmed. One old filled probe and a DIFFERENT core
# pending order stay probe; new stock X hypothetically requests confirmed.
old=[row('Y'+str(k),'T'+str(k),'confirmed','mobile',800,'100','99') for k in range(5)]
old+=[row('P','S','probe','core',200,'50','45'),row('A','S','probe','core',100,'50','40',pending=True,status='open')]
cash=D(590000);new=row('X','S','confirmed','mobile',400,'50','45',pending=True,status='open')
assert new['qty']*new['mark']==D('.02')*NAV
assert J.LR.protection_risk(100,D(50),D(40),schedule,D(1))<=D('.0025')*NAV
before=check(old,cash);after_rows=copy.deepcopy(old)+[new];after=check(after_rows,cash)
assert all(after['checks'].values())
assert before['probe']==after['probe']
assert before['sector_S']['capital']<=D('.02')*before['budget_NAV']
assert after['sector_S']['capital']>D('.02')*after['budget_NAV']
assert after['total']['capital']-before['total']['capital']==D(20000)
assert after['total']['risk']-before['total']['risk']==D(2000)
pending_blocks_original_migration=any(r['sector']=='S' and r['attempt']=='current' and r['pool']=='probe' and r['pending'] and r['status'] in ['open','cancel_pending'] for r in old)
assert pending_blocks_original_migration
cancel_pending=copy.deepcopy(after_rows);next(r for r in cancel_pending if r['stock']=='A')['status']='cancel_pending'
assert check(cancel_pending,cash)==after
ack=[r for r in cancel_pending if r['stock']!='A'];ack_state=check(ack,cash);transfer=copy.deepcopy(ack)
for r in transfer:
    if r['sector']=='S' and r['attempt']=='current' and r['pool']=='probe' and not r['pending']:r['pool']='confirmed'
transferred=check(transfer,cash)
assert ack_state['total']==transferred['total'] and ack_state['available_after_reserves']==transferred['available_after_reserves']
assert all(transferred['checks'].values())
assert ack_state['probe']['capital']-transferred['probe']['capital']==transferred['confirmed']['capital']-ack_state['confirmed']['capital']==D(10000)

# Example 2: no pending order; migrating ALL old probes is too large, whereas
# a new confirmed legal minimum still fits. No old resource is released.
old2=[row('Z'+str(k),'U'+str(k),'confirmed','mobile',7375,'10','9.9') for k in range(8)]
old2+=[row('Q','S','probe','core',380,'50','45')]
cash2=D(391000);minimum=row('X','S','confirmed','mobile',100,'50','45',pending=True,status='open')
b2=check(old2,cash2);a2=check(old2+[minimum],cash2)
assert b2['confirmed']['capital']+b2['probe']['capital']>D('.6')*NAV
assert all(a2['checks'].values()) and b2['probe']==a2['probe']

# Negative control: counting only the confirmed portion of an industry's cap
# would launder capacity. The original all-pool industry formula still rejects.
bad=[row('P','S','probe','core',380,'50','49'),row('C','S','confirmed','mobile',1600,'50','49'),row('X','S','confirmed','mobile',300,'50','49',pending=True,status='open')]
bad_result=check(bad,D(901000));assert resources(bad,'confirmed','S')['capital']==D(95000)
assert bad_result['sector_S']['capital']==D(114000) and not bad_result['checks']['sector_S_capital']

payload=dict(scope='manual conservation examples; not an alternative allocator or policy test, no admission/request/fill',passed=True,original_fee_schedule=sd,
    example_pending_probe=dict(original_migration_guard_blocks=pending_blocks_original_migration,before=before,hypothetical_new_confirmed=after,cancel_request_no_release=check(cancel_pending,cash),after_cancel_ack=ack_state,after_separate_legal_transfer=transferred,
        further_probe_request_must_still_fail_all_pool_industry_two_percent=True,
        core_role_preserved=True,loss_scope='no loss ledger modeled; proposal must retain original cumulative records, not proven by this arithmetic example'),
    example_whole_transfer_too_large=dict(before=b2,hypothetical_new_confirmed_minimum=a2,old_probe_retained=True),
    invalid_variant_ignoring_probe_industry_occupancy=bad_result,
    no_policy_code_implemented=True,no_local_planner_rerun=True,no_economic_paths=True,
    source_hashes={str(rulespath):hashlib.sha256(rulespath.read_bytes()).hexdigest(),str(Path(J.LR.__file__)):hashlib.sha256(Path(J.LR.__file__).read_bytes()).hexdigest()})
(O/'RESOURCE_CONSERVATION_EXAMPLES.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n')
print('RESOURCE_ARITHMETIC_VERIFIED',float(after['total']['capital']),float(after['total']['risk']),float(after['pending_fees']))
