"""Thin joins and boundary checks of existing native baseline measurements."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D,getcontext
import json,gzip,hashlib
getcontext().prec=65
HERE=Path(__file__).resolve().parent;E=HERE.parents[1];P=HERE/'results_v2';C=E/'dec2022_authorization_v1/account_comparison/results_v1';SRC={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 with (P/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-6'),(k,a,b)
matrix=read(P/'STAGE_WEALTH_CAPITAL_MATRIX.json');metrics={x['period']:x for x in matrix};old=read(E/'dec2022_authorization_v1/followup_robustness_v1/performance/results_v1/FIXED_PERIOD_PERFORMANCE.json');old={(x['period']):x for x in old if x['arm']=='BASELINE'}
matching={'FULL_2022_2024':'full_2022_2024','YEAR2022':'2022','YEAR2023':'2023','YEAR2024':'2024','P03_Dec2022':'Dec2022','P04_2023JanApr':'2023_Jan_Apr','P07_2024FebMay':'2024_Feb_May','P10_after2024Oct8':'after_2024_10_08','VIEW_from924_to_yearend':'from_2024_09_24','STRONG_2025Jul_2026Jun':'strong'}
for name,prior in matching.items():
 for k in ['NAV_begin','NAV_end','net_wealth_change','strict_realized_change','open_unrealized_change','AR_change','fees','buy_gross','sell_gross','period_rebased_max_DD','maximum_account_DD_from_entire_account_path_peak','mean_CLOSE_exposure','mean_previous_CLOSE_exposure']:eq(metrics[name][k],old[prior][k],'sealed performance '+name+' '+k)
raw=read(E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/daily.jsonl.gz',gz=True,lines=True);part=[x for x in matrix if x['is_disjoint_partition_member']];daily_membership=[]
for d in raw:
 matches=[x['period'] for x in part if x['start']<=d['at'][:10]<=x['end']];assert len(matches)==1;daily_membership.append(dict(at=d['at'],partition=matches[0],native_NAV=d['nav']))
assert len(daily_membership)==726
save('DISJOINT_NATIVE_CALENDAR_AND_SEALED_CROSSCHECK.json',dict(status='PASS',partition_native_CLOSEs=726,every_original_CLOSE_assigned_exactly_once=True,sealed_baseline_views_compared=matching,metric_fields_compared=15,membership=daily_membership,new_accounts=0))
campstats={}
for win in ['2022_2024','strong']:
 cc=read(P/f'{win}_CAMPAIGNS_FULL_ACCOUNTING.json');negative=sorted([c for c in cc if D(c['endpoint_net'])<0],key=lambda c:D(c['endpoint_net']));positive=[c for c in cc if D(c['endpoint_net'])>0];grossneg=-sum((D(c['endpoint_net']) for c in negative),Z)
 campstats[win]=dict(campaigns=len(cc),closed=sum(c['closed'] is not None for c in cc),open=sum(c['closed'] is None for c in cc),negative_campaigns=len(negative),positive_campaigns=len(positive),gross_negative=-grossneg,gross_positive=sum((D(c['endpoint_net']) for c in positive),Z),net=sum((D(c['endpoint_net']) for c in cc),Z),
  top_negative={str(n):dict(campaign_ids=[c['campaign_id'] for c in negative[:n]],negative_amount=sum((D(c['endpoint_net']) for c in negative[:n]),Z),fraction_of_all_negative_campaign_amount=None if not grossneg else -sum((D(c['endpoint_net']) for c in negative[:n]),Z)/grossneg) for n in [1,5,10,20]},
  limitation='Endpoint actual campaign contributions, open marked separately. Representative chains explain mechanisms but are not the full denominator, causal losses, or feasible deletion returns.')
save('CAMPAIGN_LOSS_BREADTH.json',campstats)
# Dec boundary: only actual holdings known Nov30 and already-closed actual layers.
cc=read(P/'2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json');layers=read(C/'BASELINE_2022_2024_LAYERS.json');byid={x['layer_in_this_book']:x for x in layers};decrows=read(C/'BASELINE_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');held={x['layer_in_this_book']:x for x in decrows if x['cohort']=='old_inventory_Nov30'};boundary='2022-11-30T15:10:00+08:00';cases=[]
for c in cc:
 ids=set(c['layer_ids']);hh=[held[lid] for lid in ids if lid in held];past=[byid[lid] for lid in ids if byid[lid]['closed'] is not None and byid[lid]['closed']<=boundary]
 prior_held={k:sum((D(x['Nov30_components'][k]) for x in hh),Z) for k in ['real','unreal','AR','wealth']}
 closed_real=sum((D(x['strict_realized']) for x in past),Z);closedAR=sum((D(x['AR']) for x in past),Z);delta=c['stage_wealth']['P03_Dec2022']
 if not hh and not any(D(v) for v in delta.values()):continue
 cases.append(dict(campaign_id=c['campaign_id'],sid=c['sid'],name=c['name'],industry=c['industry'],opened=c['opened'],closed=c['closed'],layer_ids=c['layer_ids'],Nov30_actually_held_layers=len(hh),Nov30_held_components=prior_held,Nov30_prior_closed_same_campaign_real=closed_real,Nov30_prior_closed_same_campaign_AR=closedAR,
  Nov30_known_campaign_wealth=prior_held['wealth']+closed_real+closedAR,Nov30_remaining_inventory_unreal_sign='profit' if prior_held['unreal']>0 else 'loss' if prior_held['unreal']<0 else 'flat_or_no_held',Dec_campaign_components=delta,
  actual_full_campaign_endpoint_net=c['endpoint_net'],endpoint_used_only_as_evaluation_not_Nov30_input=True))
save('DEC_OLD_INVENTORY_KNOWN_PROFIT_AND_CAMPAIGNS.json',dict(source_clock='Nov30 actual native CLOSE. Held comps from audited original Dec rows; closed parts only actual closed<=Nov30, no terminal labels put into open layers.',actual_old_layers=87,
 Nov30_gross_positive_held_unreal=sum((max(Z,D(r['Nov30_components']['unreal'])) for r in held.values()),Z),Nov30_gross_negative_held_unreal=sum((min(Z,D(r['Nov30_components']['unreal'])) for r in held.values()),Z),Nov30_net_held_unreal=sum((D(r['Nov30_components']['unreal']) for r in held.values()),Z),
 rows=sorted(cases,key=lambda x:D(x['Dec_campaign_components']['wealth'])),limitation='Positive profit at known start and later decline is not proof exit was early/late or the CLOSE peak was executable; later new allocations are separate actual flows.'))
sourcefiles=[E/'trend_exit_controls_v1/runs/BASELINE'/w/'RUN_METADATA.json' for w in ['2022_2024','strong']]
for p in sourcefiles:
 meta=read(p);assert meta['arm']=='BASELINE' and meta['fresh_cash']==1000000 and not meta['yearly_reset']
pilot=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py');SRC[str(pilot)]=sha(pilot);assert "if a.risk_state['on']:" in pilot.read_text()
save('CAUSAL_AND_EXECUTION_BOUNDARIES.json',dict(financial_partition='P01..P10 each native CLOSE once; YEAR/H2/ACT/other VIEW rows overlap and cannot be added. Strong independent starting1m is a separate account, not appended to weak account.',
 five_hypotheses='Starting signal recognition, sizing, exit direction, recovery/pause and concentration are overlapping mechanisms. No causal five-way additive monetary decomposition is identified from one observed account.',
 exit_peak='Recorded held-CLOSE pure unreal and recognized campaign peaks are descriptive and may be negative. Cannot sell at that same CLOSE once observed; a changed order would require next lawful execution, actual sellable quantity/fees/capacity/price. Changed cash/ACT/entries propagate; per-event static differences cannot be summed as account profit.',
 pause='Paused flat dates are account observations. Original ACT-off branch records no funded buy intents; that is not evidence of zero market signals. Existing logs do not identify the alternative fundable/intended portfolio, so broad market returns cannot be called missed profit. Pending buys signaled before pause may execute on a day ending ACT off; clocks retained.',
 core_scale='Decision CLOSE actually-funded CORE q>0 must be separate from same-CLOSE CORE intent and next-OPEN simultaneous core/mobile fills. Shared source decision_features has nominal line risk and original frozen order; mobile2% is gross target, not a2% loss-risk budget. Dedicated scale_concentration audit computes these funded CORE fields.',
 source='Original No60 BASELINE2265+1171 only; H2 helper module reused strictly as read-only audited snapshot/period mathematics, no H2 financial book or alternate path consumed.',
 costs_and_cash='Actualfees already enter net wealth; actual buycash is turnover, not concurrent capital. AR is recognized receivable, not proven paid cash. No isolated fee addback is called re-run return.',
 new_accounts=0,new_account_events=0,sealed_files_modified=False))
SRC[str(Path(__file__).resolve())]=sha(__file__);save('SUPPLEMENT_SOURCE_SHA256.json',SRC)
print('BASELINE_SUPPLEMENT_PASS',len(cases),'Dec active campaigns',len(matching),'old performance views')
