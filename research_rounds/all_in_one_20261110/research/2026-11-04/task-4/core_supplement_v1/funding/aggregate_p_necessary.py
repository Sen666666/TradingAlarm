"""Light read of already completed P context. No new prices or state prep."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import gzip,json,time
O=Path(__file__).resolve().parent
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 t=time.monotonic();meta=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text());semis={s for s,r in meta.items()if r['industry']=='半导体'};assert len(semis)==126
 pmap={(p['window'],p['sid'],p['day']):p for p in json.loads((O.parent/'P_EVENTS.json').read_text())}
 groups=defaultdict(Counter);ids=defaultdict(lambda:defaultdict(set));ap=[];residual=[];warm_residual=[];changed=[];positive=[];compared=0
 for line in gzip.open(O/'P_ORIGINAL_RESOURCE_CONTEXT.jsonl.gz','rt'):
  x=json.loads(line);isB=x['state']=='B_I_on_no_i_buy';h1=x['window']=='strong'and x['day']>='2026-01-01';semi=x['sid']in semis
  if semi and h1 and x['state'].startswith('A'):
   z=dict(x,name=meta[x['sid']]['name'],price_event=pmap[x['window'],x['sid'],x['day']]);ap.append(z)
  if not isB:continue
  q=x['B_minimum_unit_necessary_only']or{};s=x.get('original_S0');safe=None
  if s and 'OPEN_minimum_gross'in q:
   # Currency safety cushions exceed native 1e-9 float comparison tolerance.
   margin=D(s['actual_sector_inventory_capital'])+D(q['OPEN_minimum_gross'])-D('.02')*D(s['optimistic_NAV_upper'])
   safe_margin=D(s['actual_sector_inventory_capital'])+D(q['OPEN_minimum_gross'])-D('.02')*(D(s['optimistic_NAV_upper'])+D('.000001'))-D('.000001')
   safe=safe_margin>0;compared+=1
   if margin>0:positive.append(margin)
   if safe!=bool(q['certified_sector_capital_failure_even_optimistic_NAV']):changed.append(dict(window=x['window'],sid=x['sid'],day=x['day'],raw_margin=margin,safe_margin=safe_margin))
  intersection=x['B_flat_ACT_S0_epoch_pending_intersection'];sp=bool(q.get('signal_minimum_risk_and_2pct_cap_pass'));op=bool(q.get('OPEN_minimum_risk_and_2pct_necessary_pass'));cash=bool(q.get('isolated_original_S0_cash_can_pay_minimum'))
  not_eliminated=intersection and sp and op and cash and safe is False
  warm=x['G1']['current_category']=='G1_warm_no_fresh'
  scopes=[x['window']]+(['H1_2026']if h1 else[])
  for scope in scopes:
   domains=['all1709']+(['semiconductor126']if semi else[])
   for domain in domains:
    key='|'.join([scope,domain,x['G1']['current_category']]);c=groups[key];c['B_price_events']+=1
    if not intersection:continue
    c['flat_ACT_otherS0_noPending_COREunconsumed']+=1;ids[key]['stocks'].add(x['sid']);ids[key]['E0_segments'].add((x['sid'],pmap[x['window'],x['sid'],x['day']]['source_segment'],x['e0_run_start']))
    same=x['original_CP_same_day']is not None;nc=x['next_original_CP'];c['CP_same_day']+=same;c['no_CP_same_day']+=not same;c['later_CP_same_I_epoch']+=nc is not None and nc['same_native_I_epoch'];c['no_same_CP_but_later_CP_same_I']+=not same and nc is not None and nc['same_native_I_epoch']
    c['signal_minimum_pass']+=sp;c['OPEN_minimum_necessary_pass']+=op;c['isolated_S0_cash_minimum_pass']+=cash;c['signal_and_OPEN_and_cash_minimum_pass']+=sp and op and cash;c['certified_sector_capital_failure_SAFE']+=safe is True;c['sector_certificate_unknown']+=safe is None;c['not_eliminated_by_minimum_cash_and_sector_tests_UPPER_ONLY']+=not_eliminated
  if semi and h1 and not_eliminated:
   z=dict(x,name=meta[x['sid']]['name'],sector_bound_safe=True,fully_admissible=False)
   residual.append(z)
   if warm:warm_residual.append(z)
 summary={k:dict(v,intersection_distinct_stocks=len(ids[k]['stocks']),intersection_distinct_source_E0_segments=len(ids[k]['E0_segments']))for k,v in groups.items()}
 save('P_B_G1_STRATIFIED_NECESSARY_SUMMARY.json',dict(groups=summary,scope='Original-path necessary tests; survivors are optimistic upper counts, never a permission or profit. Cash is shared and repeated P/E0 rows are dependent.',G1_semantics='P OR replaces composite upstream i_buy warm&&(entered||fresh). G1 warm is NOT an independent S0 field; retaining warm is a distinct diagnostic subgroup, not a new fitted gate.',new_marks=0,new_accounts=0,seconds=time.monotonic()-t))
 save('P_SECTOR_BOUND_TOLERANCE_AUDIT.json',dict(original_predicate_had_no_explicit_positive_cushion=True,NAV_currency_cushion='.000001',comparison_currency_cushion='.000001',native_float_tolerance='1e-9',compared=compared,reclassified=len(changed),changed=changed,minimum_raw_positive_failure_margin=str(min(positive))if positive else None,scope='Pure recheck of saved scalar caps/NAV bounds; no mark/state reconstruction or policy change'))
 save('H1_SEMICONDUCTOR_ALL8_AP_CONTEXT.json',ap);save('H1_SEMICONDUCTOR_B_RESIDUAL_UPPER_CONTEXT.json',residual);save('H1_SEMICONDUCTOR_WARM_B_RESIDUAL_UPPER_CONTEXT.json',warm_residual)
 print(json.dumps(dict(seconds=time.monotonic()-t,groups=summary,AP_events=len(ap),AP_stocks=len({r['sid']for r in ap}),H1_B_residual_upper=len(residual),H1_B_residual_warm_upper=len(warm_residual),safe_bound_reclassifications=len(changed),minimum_positive_margin=str(min(positive))if positive else None),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
