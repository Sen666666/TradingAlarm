"""Read saved Q2 opportunity/funding records; no policy or execution replay."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,collections
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import continuation as E
J=E.J;L=E.L
META=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
TARGET={'URFI881172','URFI881270','URFI881121'}
def stream(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
result=[]
for ref in ('B3','B_diag'):
 root=O/'runs'/ref/'pair';a=obj(root/'B.json.gz');daily=[r for r in stream(root/'daily.jsonl.gz') if r['at'][:10]>='2026-04-01'];bysector=collections.defaultdict(list)
 for r in stream(root/'opportunities.jsonl.gz'):
  if r['day']>='2026-04-01' and r['sector'] in TARGET:bysector[r['sector']].append(r)
 funding=list(r for r in stream(root/'funding.jsonl.gz') if r['at'][:10]>='2026-04-01' and META[r['sid']]['sector_id'] in TARGET)
 for g in sorted(TARGET):
  opp=bysector[g];fund=[r for r in funding if META[r['sid']]['sector_id']==g];fresh={r['CP1_id'] for r in opp if r['CP1_id'] and r['mobile_Q'] is True};reserved={r['CP1_id'] for r in fund if r['role']=='mobile' and r['result']=='reserved' and r.get('CP1_id')};fills={x['CP1_id'] for x in a['journal'] if x['kind']=='real_buy_fill' and x['role']=='mobile' and x['CP1_id'] in fresh and x['at'][:10]>='2026-04-01'}
  cores=[r for r in opp if r['core_Q'] is True];mobile=[r for r in opp if r['CP1_id'] and r['mobile_Q'] is True];legal=[r for r in opp if r['roles'] and not r['barriers']]
  result.append(dict(reference=ref,sector=g,first_visible_original_I_Q_true=min((r['day'] for r in cores),default=None),first_visible_fresh_CP1_Q_true=min((r['day'] for r in mobile),default=None),first_role_with_no_recorded_account_barrier=min((r['day'] for r in legal),default=None),Q2_distinct_fresh_CP1_with_Q_true=len(fresh),Q2_fresh_receipts_reserved=len(fresh&reserved),Q2_fresh_receipts_with_actual_fill=len(fresh&fills),fresh_CP1_Q_unknown=sum(bool(r['CP1_id']) and r['mobile_Q'] is None for r in opp),funding_record_counts=dict(collections.Counter((r['role'],str(r['result'])) for r in fund)),barrier_stockdays=dict(collections.Counter(x for r in opp if r['CP1_id'] for x in r['barriers'])),counts_not_independent_trials=True,March31_carry_intent_fills_excluded_from_Q2fresh_denominator=True,reason_strings_can_contain_joint_constraints=True))
 risk=[(D(str(r['pool_probe'][1]))+D(str(r['pool_confirmed'][1])))/D(r['nav'])*100 for r in daily]
 capital=L.read(O/'analysis'/ref/'DAILY_CAPITAL_BEHAVIOR.json')
 stats=dict(reference=ref,Q2_mean_nominal_floor_risk_pct=str(sum(risk,D(0))/len(risk)),Q2_peak_nominal_floor_risk_pct=str(max(risk)),mean_held_industry_count=sum(r['held_industries'] for r in capital)/len(capital),max_held_industry_count=max(r['held_industries'] for r in capital),mean_top3_industry_share_of_inventory=sum(D(r['top3_industry_share_of_inventory']) for r in capital)/len(capital),mean_held_while_industry_attempt_inactive_pct=sum(D(r['industry_no_new_attempt_but_still_held_pct']) for r in capital)/len(capital),not_a_new_exit_rule=True)
 E.IO.write_json(O/'analysis'/ref/'CAPITAL_STATE_STATS.json',J.W.canon(stats))
E.IO.write_json(O/'THREE_CASE_SIGNAL_FUNDING_FUNNELS.json',J.W.canon(result))
for r in result:print(r['reference'],r['sector'],'fresh/reserved/filled',r['Q2_distinct_fresh_CP1_with_Q_true'],r['Q2_fresh_receipts_reserved'],r['Q2_fresh_receipts_with_actual_fill'])
