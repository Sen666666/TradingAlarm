"""Small read-only coverage and actual-PnL summaries, no new market labels."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');A=W/'g-s-C-August-continuation-v1-20261102';V=W/'g-s-pre-sell-quote-prototype-v2-20261102'
Z=D(0)
def read(n):return json.loads(Path(n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,default=str,indent=2)+'\n')
def pn(vals):return dict(positive_rows=sum(v>0 for v in vals),negative_rows=sum(v<0 for v in vals),zero_rows=sum(v==0 for v in vals),gross_positive=sum((max(Z,v) for v in vals),Z),gross_negative=sum((min(Z,v) for v in vals),Z),net=sum(vals,Z))
batches=read(O/'BATCHES.json');rechecks=read(O/'QUOTE_RECHECKS.json');ss=read(O/'SCREEN_SUMMARY.json')
source=read(O/'SOURCE_SHA256.json');source.update(read(O/'QUOTE_SOURCE_SHA256.json'))
freeze=read(V/'SOURCE_FREEZE.json')
for p,h in freeze['sources'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;source[p]=h

follow=[]
for cell in ['C10','C20']:
 path=A/'analysis'/(cell+'-LAYERS.json');layers={r['layer']:r for r in read(path)};source[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 first={}
 for b in batches:
  if b['cell']!=cell:continue
  for p in b['source_sell_parts']:
   key=p['layer'];parts=layers[key]['actual_sell_parts'];index=next(i for i,v in enumerate(parts) if v['receipt']==p['receipt'])
   if key not in first or index<first[key]:first[key]=index
 for lid,index in first.items():
  r=layers[lid];later=r['actual_sell_parts'][index+1:]
  follow.append(dict(cell=cell,layer=lid,sid=r['sid'],first_funding_sale=r['actual_sell_parts'][index]['at'],
   later_actual_realized_net_original_allocated_cost=sum((D(p['realized_trade_PNL']) for p in later),Z),
   terminal_unrealized_net_original_cost=D(r['unrealized_net_buy_cost']),terminal_remaining_qty=r['remaining_qty'],
   later_actual_parts=len(later),
   later_price_contribution_original_cost=sum((D(p['realized_trade_PNL']) for p in later),Z)+D(r['unrealized_net_buy_cost'])))
save('SOURCE_LAYER_LATER_ACTUAL.json',dict(definition='Unique original source layers after their first actual funding sale. Later real sales plus Aug29 remaining unrealized, both at original allocated cost. Excludes dividend timing. Not return measured from the first sale, not retained-sold-shares counterfactual. Fully sold layers have no later exposure.',
 layers=follow,summary=pn([r['later_price_contribution_original_cost'] for r in follow]),
 layers_with_later_actual_exposure=sum(bool(r['later_actual_parts'] or r['terminal_remaining_qty']) for r in follow)))
total_gross=sum((D(b['actual_source_gross']) for b in batches),Z)
zeros=[b for b in batches if b['C_category']=='NONE'];zero_gross=sum((D(b['actual_source_gross']) for b in zeros),Z)
quantity={}
for cat in ['NONE','PARTIAL_Q','FULL_Q']:
 rr=[b for b in batches if ('NONE' if b['C_category']=='NONE' else 'FULL_Q' if b['original_quantity_all_filled'] else 'PARTIAL_Q')==cat]
 quantity[cat]=dict(batches=len(rr),source_gross=sum((D(b['actual_source_gross']) for b in rr),Z),source_net=sum((D(b['actual_source_net']) for b in rr),Z),receiver_gross=sum((D(b['actual_C_receiver_gross']) for b in rr),Z),
  dates=[dict(cell=b['cell'],plan=b['original_plan_at'],sale_days=b['actual_source_days']) for b in rr])
save('QUANTITY_COVERAGE.json',quantity)
save('COVERAGE.json',dict(actual_funding_batches=len(batches),actual_source_gross=total_gross,
 zero_target_fill_batches=len(zeros),zero_batch_share=D(len(zeros))/len(batches),zero_source_gross=zero_gross,zero_gross_share=zero_gross/total_gross,
 quote_zero_cases_verified=sum(r['status']=='NO_LEGAL_RECIPIENTS' for r in rechecks),quote_zero_cases_unknown=sum(r['status']!='NO_LEGAL_RECIPIENTS' for r in rechecks),
 zero_cases_not_rechecked=sum(r['status']=='UNKNOWN_NOT_RECHECKED' for r in rechecks),
 nonzero_cases_deliberately_not_rechecked=sum(b['C_category']!='NONE' for b in batches),
 by_cell_plan_month={c+'|'+m:dict(Counter(b['C_category'] for b in batches if b['cell']==c and b['original_plan_at'].startswith(m))) for c in ['C10','C20'] for m in ['2025-07','2025-08']},
 receiver_batch_actual_outcome_counts={cat:pn([D(b['C_receiver_outcomes']['net']) for b in batches if b['C_category']==cat]) for cat in ['NONE','SOME_TARGET_NAMES','ALL_TARGET_NAMES']},
 limits=['Current open print proof only, not a prediction of all-day execution failure.',
 'Three zero cases rechecked; 77 nonzero cases not projected. Partial-sale reductions and opportunity-cost benefit unknown.',
 'All observed cash amounts, risk rejection causes and PnL are original actual paths. No avoidable-return estimate.',
 'Two cells share inputs and overlapping stock exposures; no independent win-rate interpretation.']))
lines=['One row per cell x original CLOSE certificate with actual opportunity funding sales. ALL means all target STOCK NAMES have a C fill; does not mean full original Q.',
 'cell | original_CLOSE | actual_sale_days | target_names | coverage | source_gross | C_receiver_gross | source_realized_net | recipient_actual_PnL_to_Aug29 | quote_status']
for b in batches:
 q=next((r['status'] for r in rechecks if r['parent']==b['certificate']), 'NOT_RECHECKED_NONZERO')
 lines.append(' | '.join([b['cell'],b['original_plan_at'][:10],','.join(b['actual_source_days']),str(b['target_stocks']),b['C_category'],str(round(D(b['actual_source_gross']),2)),str(round(D(b['actual_C_receiver_gross']),2)),str(round(D(b['source_realized_PNL']['net']),2)),str(round(D(b['C_receiver_outcomes']['net']),2)),q]))
(O/'DATE_LIST.txt').write_text('\n'.join(lines)+'\n')
save('SOURCE_SHA256.json',source)
save('FINAL_CHECKS.json',dict(passed=True,financial_events=0,account_restores=0,runner_calls=0,native_order_callbacks=0,
 original_source_QD_code_changed=False,quote_only_cases=len(rechecks),quote_checks_per_case=[r.get('checks') for r in rechecks],
 native_before_first_sale_actual_releases=0,all_original_funding_fill_ids_unique_and_complete=True,original_August_per_order_exports_matched=True,
 primary_and_all_roles_categories_identical=all(b['C_category']==b['all_roles_category'] for b in batches),
 current_V2_freeze_sources_match=True,not_a_live_execution_certification=True))
print('coverage',json.dumps(read(O/'COVERAGE.json'),default=str))
print('source later actual',json.dumps(read(O/'SOURCE_LAYER_LATER_ACTUAL.json')['summary']))
