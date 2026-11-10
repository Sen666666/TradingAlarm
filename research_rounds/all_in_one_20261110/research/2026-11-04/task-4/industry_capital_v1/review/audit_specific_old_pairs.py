"""Per-stock opportunity-cost decomposition; saved-only, no new prices or paths."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
import ast,gzip,json,hashlib,time
R=Path(__file__).resolve().parent;I=R.parent;Z=D(0);ONE=D(1);SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt')as h:
  for s in h:yield json.loads(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
t0=time.monotonic();ns=globals();rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');src=ast.parse((R/'audit_matched_saved.py').read_text());func=[n for n in src.body if isinstance(n,ast.FunctionDef)and n.name in ['dec','eff','fee','liq']];exec(compile(ast.Module(body=func,type_ignores=[]),'<review_pure_fee_functions>','exec'),ns)
matched={r['key']:r for r in rows(I/'MATCHED_WITH_EXANTE.jsonl.gz')};sums=defaultdict(lambda:[Z,Z,Z]);seen=set();pa=[]
for p in rows(I/'SPECIFIC_OLD_STOCK_PAIRS.jsonl.gz'):
 k=p['key'],p['old_sid'];assert k not in seen;seen.add(k);m=matched[p['key']];assert m['matched_status']=='known_conditional_match';sid=p['old_sid'];ref=next(z for z in m['old_all']['mark_references']if z['sid']==sid);layers=[x for x in m['old_all']['layers_detail']if x['sid']==sid];point=next(x for x in m['exante']['old_stocks']if x['sid']==sid)
 g0=dec(ref['initial_qty'])*dec(ref['OPEN_mark']);l0=liq(sid,m['OPEN'],dec(ref['initial_qty']),dec(ref['OPEN_mark']));vh=sum((dec(x['actual_sale_net_wealth_after_anchor'])+dec(x['new_dividend_entitlement_after_anchor'])for x in layers),Z)+liq(sid,m['new']['horizon_CLOSE_day'],dec(ref['terminal_qty']),dec(ref['terminal_mark']));assert dec(p['G0'])==g0 and dec(p['L0'])==l0 and dec(p['Vh'])==vh
 nr=dec(m['new_net_return_pct']);orr=(vh/g0-1)*100;assert dec(p['candidate_return_pct'])==nr and dec(p['old_return_pct'])==orr
 quad='zero_boundary'if nr==0 or orr==0 else('new_profit'if nr>0 else'new_loss')+'_'+('old_profit'if orr>0 else'old_loss');assert p['quadrant']==quad
 cn=dec(m['new']['entry_cash_actual']);vn=dec(m['new']['wealth_from_invested_Cn_net_liquidation']);assert dec(p['equal_cash_gap'])==vn-cn*vh/l0
 b=m['release_bound'];rel=dec(b['required_sector_relief_lower_bound_SAFE'])if b['release_amount_status']=='KNOWN_NECESSARY_BOUND'else None
 if rel is not None:assert dec(p['required_relief_scenario_gap'])==(vn-cn)-(rel/g0)*(vh-l0)
 assert p['old_features']==point and p['candidate_COR_new_ok']==m['exante']['candidate']['COR_new_ok']and p['old_COR_weak']==point['COR_weak'];cap=bool(rel is not None and rel<=g0 and not point['prior_CLOSE_exit_lock']and not point['prior_layer_exit_reason']and not b.get('qmin_itself_exceeds_sector_allowance_SAFE',True));assert cap==p['single_old_stock_not_ruled_out_by_capital']
 for j,v in enumerate([g0,l0,vh]):sums[p['key']][j]+=v
 pa.append(p)
assert len(pa)==17875 and len(sums)==7282
maxdiff=Z
for k,v in sums.items():
 for j,field in enumerate(['G0','L0','Vh']):
  delta=abs(v[j]-dec(matched[k]['old_all'][field]));assert delta<D('1e-19'),(k,field,delta);maxdiff=max(maxdiff,delta)
weak=[p for p in pa if p['candidate_COR_new_ok']is True and p['old_COR_weak']is True];cap=[p for p in weak if p['single_old_stock_not_ruled_out_by_capital']];assert len(weak)==23 and len({p['key']for p in weak})==22 and len(cap)==6 and Counter(p['quadrant']for p in cap)==Counter(new_loss_old_loss=5,new_profit_old_profit=1)
assert read(I/'ALL_FIXED_COR_WEAK_STOCK_PAIRS.json')==weak
for s in read(I/'SPECIFIC_OLD_STOCK_SUMMARY.json'):
 a=[p for p in(pa if s['group']=='all_old_stock_pairs'else weak)if p['window']==s['window']];cp=[p for p in a if p['single_old_stock_not_ruled_out_by_capital']];assert s['stock_pairs']==len(a)and s['distinct_candidate_events']==len({p['key']for p in a})and Counter(s['quadrants'])==Counter(p['quadrant']for p in a);assert s['capital_not_excluded_pairs']==len(cp)and s['capital_not_excluded_events']==len({p['key']for p in cp})and Counter(s['capital_not_excluded_quadrants'])==Counter(p['quadrant']for p in cp);assert s['pure_industry_pairs']==sum(p['classification']in ['sector_capital_only','both_sector_only']for p in a)
res={'passed':True,'scope':'All17875 saved candidate/actual-old-stock decompositions, independently recomputed dated per-stock fees and values, original basket sum and frozen COR23-pair subset; no marks/paths/ledgers.','pairs':17875,'candidate_events':7282,'G0_L0_Vh_equal_basket_sums_within_Decimal_roundoff':True,'max_sum_roundoff_currency':str(maxdiff),'weak_stock_pairs':23,'weak_stock_candidate_events':22,'single_stock_capital_not_excluded_weak_pairs':6,'six_pair_quadrants':dict(Counter(p['quadrant']for p in cap)),'six_pair_new_profit_old_loss':0,'per_stock_fee_charged_once_in_saved_formula':True,'all_summary_counts_exact':True,'not_donor_or_economic_permission':['Gross capacity is only necessary; actual FIFO/T+1/CA-lock/fees/cash/probe/sector-risk and same-order duties remain unproved.','Pair comparisons reuse stocks/events; not23independent trades, and no future outcome chooses a donor.','Fractional scale at required-relief bound is a descriptive scenario and may exceed available stock.'],'reviewer_new_marks':0,'reviewer_new_ledgers':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),I/'analyze_specific_old_stocks.py',I/'SPECIFIC_OLD_STOCK_PAIRS.jsonl.gz',I/'SPECIFIC_OLD_STOCK_SUMMARY.json',I/'ALL_FIXED_COR_WEAK_STOCK_PAIRS.json']},'seconds':time.monotonic()-t0};(R/'SPECIFIC_OLD_STOCK_PAIRS_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k not in ['source_sha256','not_donor_or_economic_permission']},indent=2))
