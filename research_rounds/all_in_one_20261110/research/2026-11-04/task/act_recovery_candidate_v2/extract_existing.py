"""Bounded read-only extraction: existing primitive books and cached price facts only.
No Account, native producer imports, prices, indicators, or counterfactual PnL.
"""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent

def load(p):
    with (gzip.open(p, 'rt') if str(p).endswith('.gz') else open(p)) as f:
        return json.load(f)

paths = {
    'static20': ROOT/'ar6_native_feasibility/market_recovery_three_state/diagnostic_v2/FULL_ORIGINAL_INPUT_PLUS_STATIC20.csv',
    'B_book': ROOT/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz',
    'D_book': ROOT/'market_gross_admission_native_v1/full-long-v1/pair/D_GROSS10.json.gz',
    'D_opportunities': ROOT/'market_gross_admission_native_v1/full-long-v1/pair/opportunities.jsonl.gz',
    'own_wait': ROOT/'market_gross_admission_outcome_analysis_v1/full_long_v1/OWN_ACT_RECOVERY_WAIT_PATH.json',
    'old_cycles': ROOT/'ar6_native_feasibility/market_recovery_three_state/diagnostic_v2/ALL_ORIGINAL_PAUSE_CYCLES.json',
    'old_recovery_results': ROOT/'pvr_pool_feasibility/a_recovery_full_diagnostic/OLD_RECOVERY_NEGATIVE_CONTROLS.json',
    'A_readout': ROOT/'pvr_pool_feasibility/a_recovery_full_diagnostic/READOUT.txt',
    'three_state_readout': ROOT/'ar6_native_feasibility/market_recovery_three_state/READOUT.txt',
    'daily_support_readout': ROOT/'ar6_native_feasibility/market_recovery_three_state/structural_walk_daily_support_v2/READOUT.txt',
    'rms_readout': ROOT/'ar6_native_feasibility/market_recovery_three_state/noise_rms63_single_check/READOUT.txt',
    'prior_H_card': ROOT/'pvr_pool_feasibility/ma63_incremental_rights_card_v1/H_RECOVERY_MA63_NEW20_NECESSARY_CARD.txt',
    'H_boundary': ROOT/'pvr_pool_feasibility/ma63_incremental_rights_card_v1/H_TRIP_AND_RECOVERY_BOUNDARY.txt',
    'risk_policy': Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py'),
    'joint_source': Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py'),
    'compute_recovery': Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/market-proof-lifecycle-readonly-20261101/ORIGINAL_COMPUTE_RECOVERY.py'),
    'REC_prepare': Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/recovery-only-20261027/code/prepare.py'),
    'REC_protocol': Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/recovery-only-20261027/PROTOCOL.md'),
}
freeze={k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()}
(OUT/'INPUT_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
static=list(csv.DictReader(paths['static20'].open()))
byday={x['day']:x for x in static}
calendar=[x['day'] for x in static]
wait=load(paths['own_wait'])
cycles=[]
facts={}
for key,label in [('B_book','ARCHIVED_B'),('D_book','D_GROSS10')]:
    b=load(paths[key])
    risk=[x for x in b['audit'] if x['kind']=='risk_checkpoint']
    assert len(risk)==726
    for checkpoint in risk:
        source=byday[checkpoint['at'][:10]]
        assert checkpoint['fast']==(source['fast_on']=='True')
        assert checkpoint['breakout']==(source['breakout']=='True')
    facts[label]={'pause_count':sum(x.get('event')=='pause' for x in risk),'risk_checkpoints':726}
    for pause in (x for x in risk if x.get('event')=='pause'):
        after=[x for x in risk if x['at']>=pause['at']]
        resume=next((x for x in after if x.get('event')=='resume'),None)
        end=resume['at'] if resume else risk[-1]['at']
        within=[x for x in after if x['at']<=end]
        flat=next((x for x in within if x['flat']),None)
        eligible=[x for x in within if x['flat'] and not x['on']]
        early=[dict(byday[x['at'][:10]],original_context_at=x['at'],original_context_NAV=x['nav'])
               for x in eligible if byday[x['at'][:10]]['trigger20']=='True']
        firstbuy=next((t for t in b['trades'] if t['side']=='buy' and resume and t['at']>resume['at']),None)
        interval=next(x for x in wait[label]['pause_OPEN_intervals'] if x['original_pause_CLOSE']==pause['at'][:10])
        cycles.append(dict(account=label,pause=pause,first_flat=flat,resume=resume,
            first_subsequent_actual_buy_at=firstbuy['at'] if firstbuy else None,
            original_paused_OPEN_days=interval['paused_OPEN_days'],
            original_NOT_DOWN_paused_OPEN_days=interval['market_NOT_DOWN_but_ACT_paused_OPEN_days'],
            all_early20_paused_flat_rows=early,
            count_early20_paused_flat_days=len(early),right_censored=resume is None))
    if label=='D_GROSS10':
        facts[label]['sep24_decision']=next(x for x in b['decisions'] if x['at'].startswith('2024-09-24'))

targetdays={'2024-09-24','2024-09-25','2024-09-26'}
groups={day:dict(rows=0,core_roles=0,mobile_roles=0,only_ACT_barrier=0,other_barriers=Counter(),sids=set()) for day in targetdays}
examples=defaultdict(list)
with gzip.open(paths['D_opportunities'],'rt') as f:
    for line in f:
        r=json.loads(line)
        if r['day'] not in groups:continue
        g=groups[r['day']];g['rows']+=1;g['sids'].add(r['sid'])
        g['core_roles']+='core' in r['roles'];g['mobile_roles']+='mobile' in r['roles']
        g['only_ACT_barrier']+=r['barriers']==['ACT_paused']
        g['other_barriers'].update(x for x in r['barriers'] if x!='ACT_paused')
        if r['barriers']==['ACT_paused'] and len(examples[r['day']])<3:examples[r['day']].append(r)
for day,g in groups.items():
    g['unique_sids']=len(g.pop('sids'));g['other_barriers']=dict(g['other_barriers'])
    g['original_role_events']=g['core_roles']+g['mobile_roles']
    g['necessary_not_sufficient_examples']=examples[day]
    g['missing_for_counterfactual_execution']=['rank competition after new candidate own state','full dated quote/window/quantity/fees per candidate','aggregate slot/cash/industry/probe authorization','counterfactual reservation and actual fill']
nav=D('825930.5106910572110')
result={
 'scope':'Existing full 2022-24 No60 B and D_GROSS10 original-path causal facts. 0 new account/strategy/indicator/price. All previously seen development data, NOT OOS.',
 'cycles':cycles,'facts':facts,'D_924_retained_original_role_opportunities':groups,
 'original_D_NAV_at_first_P20':str(nav),
 'illustrative_existing_probe_gross_10pct_before_incremental_fees':str(nav*D('.10')),
 'illustrative_existing_probe_nominal_risk_005_before_incremental_fees':str(nav*D('.005')),
 'earliest_P20_observed_CLOSE':'2024-09-24 15:10:00+08:00',
 'earliest_possible_execution_OPEN':'2024-09-25 09:30:00+08:00',
 'original_D_first_execution_OPEN':'2024-09-30 09:30:00+08:00',
 'original_paused_OPENs_potentially_advanced':['2024-09-25','2024-09-26','2024-09-27'],
 'unrecoverable_same_day_OPEN_from_CLOSE_certificate':'2024-09-24',
 'counterfactual_executable_capital':'UNKNOWN; <= original 10% NAV illustration only for the first grant with unchanged original state; candidate own NAV must determine any actual cap',
 'counterfactual_account_profit_or_avoided_loss':'UNKNOWN; synthetic market change and source account profits are not candidate returns',
 'first_P20_no_summer_restarts_on_original_D_path':True,
}
assert len(cycles)==5
assert [x['day'] for x in next(x for x in cycles if x['account']=='D_GROSS10' and x['pause']['at'].startswith('2024-06-11'))['all_early20_paused_flat_rows']]==['2024-09-24','2024-09-25','2024-09-26']
(OUT/'EXISTING_FACTS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'cycles':[(x['account'],x['pause']['at'][:10],x['first_flat']['at'][:10] if x['first_flat'] else None,x['resume']['at'][:10] if x['resume'] else None,x['count_early20_paused_flat_days']) for x in cycles], 'D_opportunity_counts':{d:{k:v for k,v in g.items() if k not in ['necessary_not_sufficient_examples','missing_for_counterfactual_execution']} for d,g in groups.items()},'outputs':['INPUT_FREEZE.json','EXISTING_FACTS.json']},ensure_ascii=False))
