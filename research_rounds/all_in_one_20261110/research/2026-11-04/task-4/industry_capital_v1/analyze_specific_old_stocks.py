"""Check every real old stock as well as the basket; no donor is selected by outcome."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,hashlib,json,time
import analyze_matched_holdings as A
O=Path(__file__).resolve().parent;Z=D(0)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def main():
 start=time.monotonic();p=O/'MATCHED_WITH_EXANTE.jsonl.gz'
 with gzip.open(p,'rt')as h:rows=list(map(json.loads,h))
 pairs=[]
 for r in rows:
  if r['matched_status']!='known_conditional_match':continue
  old=r['old_all'];f={x['sid']:x for x in r['exante']['old_stocks']};by=defaultdict(list)
  for x in old['layers_detail']:by[x['sid']].append(x)
  for ref in old['mark_references']:
   sid=ref['sid'];g0=D(ref['initial_qty'])*D(ref['OPEN_mark']);l0=A.net_liquidation(sid,r['OPEN'],D(ref['initial_qty']),D(ref['OPEN_mark']))
   cf=sum((D(x['actual_sale_net_wealth_after_anchor'])+D(x['new_dividend_entitlement_after_anchor'])for x in by[sid]),Z)
   vh=cf+A.net_liquidation(sid,r['new']['horizon_CLOSE_day'],D(ref['terminal_qty']),D(ref['terminal_mark']))
   nr=D(r['new_net_return_pct']);orr=(vh/g0-1)*100;cn=D(r['new']['entry_cash_actual']);vn=D(r['new']['wealth_from_invested_Cn_net_liquidation'])
   b=r['release_bound'];rel=D(b['required_sector_relief_lower_bound_SAFE'])if b['release_amount_status']=='KNOWN_NECESSARY_BOUND'else None
   point=f[sid];sufficient=bool(rel is not None and rel<=g0 and not point['prior_CLOSE_exit_lock']and not point['prior_layer_exit_reason']and not b.get('qmin_itself_exceeds_sector_allowance_SAFE',True))
   pairs.append(dict(key=r['key'],window=r['window'],OPEN_cohort=r['period'],candidate_sid=r['sid'],old_sid=sid,
    industry=r['industry'],classification=r['classification'],candidate_COR_new_ok=r['exante']['candidate']['COR_new_ok'],old_COR_weak=point['COR_weak'],old_features=point,
    candidate_return_pct=nr,old_return_pct=orr,quadrant=A.quadrant(nr,orr),G0=g0,L0=l0,Vh=vh,
    equal_cash_gap=vn-cn*vh/l0 if l0>0 else None,
    required_relief_scenario_gap=(vn-cn)-(rel/g0)*(vh-l0)if rel is not None else None,
    single_old_stock_not_ruled_out_by_capital=bool(sufficient),
    scope='One candidate may appear with several actual old stocks; no independent/trade-count or portfolio-sum claim. Fractional donor amount is only a sensitivity, FIFO/T+1/cash/risk remain unverified.'))
 summaries=[]
 for kind,subset in [('all_old_stock_pairs',pairs),('fixed_COR_new_and_old_weak',[x for x in pairs if x['candidate_COR_new_ok']is True and x['old_COR_weak']is True])]:
  for w in ['long','strong']:
   a=[x for x in subset if x['window']==w];cap=[x for x in a if x['single_old_stock_not_ruled_out_by_capital']]
   summaries.append(dict(group=kind,window=w,stock_pairs=len(a),distinct_candidate_events=len({x['key']for x in a}),quadrants=dict(Counter(x['quadrant']for x in a)),
    capital_not_excluded_pairs=len(cap),capital_not_excluded_events=len({x['key']for x in cap}),capital_not_excluded_quadrants=dict(Counter(x['quadrant']for x in cap)),
    pure_industry_pairs=sum(x['classification']in['sector_capital_only','both_sector_only']for x in a),
    required_relief_scenario_positive=sum(x['required_relief_scenario_gap']is not None and x['required_relief_scenario_gap']>0 for x in a),
    no_action_admission=True))
 with gzip.open(O/'SPECIFIC_OLD_STOCK_PAIRS.jsonl.gz','wt')as h:
  for r in pairs:h.write(json.dumps(r,ensure_ascii=False,default=str,allow_nan=False)+'\n')
 save('SPECIFIC_OLD_STOCK_SUMMARY.json',summaries)
 save('ALL_FIXED_COR_WEAK_STOCK_PAIRS.json',[r for r in pairs if r['candidate_COR_new_ok']is True and r['old_COR_weak']is True])
 save('SPECIFIC_OLD_STOCK_SCOPE.json',dict(seconds=time.monotonic()-start,candidate_events=len(rows),known_old_pairs=len(pairs),
  economic_paths_recomputed=0,old_marks_recomputed=0,formula='Per-stock decomposition of already audited basket cash/dividend/qty and same saved native marks/dated fee schedule.',
  source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest(),str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),str(Path(A.__file__).resolve()):hashlib.sha256(Path(A.__file__).read_bytes()).hexdigest()}))
 print(json.dumps(summaries,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
