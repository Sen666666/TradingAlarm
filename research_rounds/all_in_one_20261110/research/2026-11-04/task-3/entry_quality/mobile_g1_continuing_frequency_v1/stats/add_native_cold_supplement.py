"""Append native cold formula using saved original acute_down; no grade model."""
from pathlib import Path
from decimal import Decimal as D
import csv,hashlib,json
O=Path(__file__).resolve().parent;Q=O.parents[1]
POLICY=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
state={}
for window in ['2022_2024','strong']:
 p=Q/'structural_failure_v1/state_semantics'/(window+'_ROWS.json');state[window]={r['layer']:r for r in json.loads(p.read_text())}
fields=['actual_input_gross_plus_buy_fee','actual_buy_gross','actual_buy_fee','actual_allocated_sell_fee_by_endpoint','total_actual_fees_by_endpoint','original_strict_realized','original_open_unrealized','original_dividend_AR','original_endpoint_net_contribution']
supp=[];sources={str(POLICY):sha(POLICY)}
for fn in ['A_2022_2024_MOBILE_ROWS.json','B_2026H1_NEW_MOBILE_ROWS.json','B_2025_CARRY_MOBILE_ROWS.json']:
 p=O/fn;sources[str(p)]=sha(p);rr=json.loads(p.read_text())
 for r in rr:
  s=state[r['original_account_window']][r['layer']];acute=s['original_stock_state'].get('g_acute_down');r['G1_acute_down_original_ROW']=acute
  ready=r['G1_grade_ready'];grade=r['G1_grade'];r['native_cold_original_formula']=None if ready is None or (ready and grade is None) else bool(ready and (grade<=-2 or bool(acute)))
 save(fn,rr)
 flat=[{k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in r.items()} for r in rr]
 with (O/fn.replace('.json','.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 selected=[r for r in rr if r['native_cold_original_formula'] is True]
 supp.append(dict(cohort=rr[0]['cohort'],grade_group='NATIVE_COLD_ORIGINAL_FORMULA',layers=len(selected),**{k:str(sum((D(r[k]) for r in selected),D(0))) for k in fields},fully_closed_layers=sum(r['closed_by_endpoint'] for r in selected),open_layers=sum(not r['closed_by_endpoint'] for r in selected),grade_negative_but_not_native_cold_layers=sum(r['G1_grade'] is not None and r['G1_grade']<0 and r['native_cold_original_formula'] is False for r in rr)))
save('NATIVE_COLD_SUPPLEMENT.json',dict(status='SAVED_SOURCE_FORMULA_ONLY_NO_MODEL',formula='ready and (grade<=-2 or acute_down)',source_path=str(POLICY),source_lines=[18,19],source_sha256=sources,acute_source='Already frozen ROWS.original_stock_state.g_acute_down, original decision clock equals preceding fill market CLOSE; direct grade+ready verified against facts in main audit.',groups=supp,main_LT2_and_negative_groups_unchanged=True,new_accounts=0,new_models=0,new_backtests=0))
print(json.dumps([dict(cohort=r['cohort'],native_cold=r['layers'],negative_but_not_native_cold=r['grade_negative_but_not_native_cold_layers']) for r in supp]))
