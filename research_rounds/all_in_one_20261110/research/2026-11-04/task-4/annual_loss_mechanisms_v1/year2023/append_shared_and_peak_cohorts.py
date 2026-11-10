"""Static saved-layer wealth bridge, using parent's shared actual classifications."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={};Z=D(0)
def read(p):
 p=Path(p).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 cls=read(ROOT/'annual_loss_mechanisms_v1/shared/ORIGINAL_BUY_CLASSIFICATIONS.json')
 cycles=read(ROOT/'annual_loss_mechanisms_v1/shared/ORIGINAL_POSITION_CYCLES.json')
 annual=read(ROOT/'annual_loss_mechanisms_v1/shared/ANNUAL_LAYER_WEALTH_CHANGES.json')
 ar=read(OUT/'ANNUAL_STOCK_CONTRIBUTIONS.json');dd=read(OUT/'DRAWDOWN_STOCK_CONTRIBUTIONS.json')
 saved=read(OUT/'SELECTED_FULL_STOCK_CHAINS.json');summ=read(OUT/'ACCOUNT_AND_STOCK_CONTRIBUTION_SUMMARY.json')
 stocksum=defaultdict(lambda:Z)
 for r in annual:
  if r['year']==2023:stocksum[r['sid']]+=D(r['annual_wealth_change'])
 stock_diffs={r['sid']:stocksum[r['sid']]-D(r['stock_wealth_change'])for r in ar}
 assert max(map(abs,stock_diffs.values()))<D('1e-18')
 translate={'FIRST_ACTUAL_OPEN':'first_account_entry','REOPEN_AFTER_FLAT':'reentry','HELD_ADD':'add_to_existing'}
 for s in saved:
  ids={r['layer']for r in s['original_relevant_layer_full_lifecycle_evaluation_only']}
  for t in s['original_2023_trade_chain']:
   if t['original_trade']['side']!='buy':continue
   c=cls[str(t['original_trade']['layer'])]
   assert c['actual_quantity_before_fill']==t['actual_qty_immediately_before_buy']
   assert c['classification']==translate[t['actual_quantity_classification']]
   t['root_shared_original_buy_classification']=c
   t['actual_quantity_classification']=c['classification']
  s['root_shared_position_cycles']=[r for r in cycles if r['sid']==s['sid']and set(r['layers'])&ids]
  s['root_shared_layer_annual_contributions']=[r for r in annual if r['year']==2023 and r['layer']in ids]
  assert abs(sum((D(r['annual_wealth_change'])for r in s['root_shared_layer_annual_contributions']),Z)-D(s['annual_contribution']['stock_wealth_change']))<D('1e-18')
 save('SELECTED_FULL_STOCK_CHAINS_WITH_SHARED_CYCLES.json',saved)
 peak=summ['original_boundaries'][1]
 marks={r['sid']:D(r['saved_facts_raw_close'])for r in read(OUT/'PEAK2023_05_04_ORIGINAL_STOCK_MARKS.json')['rows']}
 path=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair/B.json.gz';H[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 book=json.load(gzip.open(path,'rt'));native={r['id']:r for r in book['layers']}
 layers=[]
 for r in peak['layers']:
  l=native[r['id']];assert l['qty']==0 and l['closed'][:10]<='2023-07-21'
  wealth=D(r['cash'])+D(r['dividend'])+D(r['qty'])*marks[r['sid']]
  end=D(l['cash'])+D(l['dividend']);cohort='PEAK_EXISTING_POSITIVE_LIFECYCLE_WEALTH'if wealth>0 else'PEAK_EXISTING_NONPOSITIVE_LIFECYCLE_WEALTH'
  layers.append(dict(layer=l['id'],sid=l['sid'],cohort=cohort,peak_qty=r['qty'],peak_mark=D(r['qty'])*marks[r['sid']],peak_saved_cash=r['cash'],peak_saved_dividend=r['dividend'],peak_lifecycle_wealth=wealth,final_closed_lifecycle_wealth=end,drawdown_period_wealth_change=end-wealth,root_original_classification=cls[str(l['id'])],peak_saved_native_layer=r,terminal_closed_original_layer=l))
 for l in book['layers']:
  if not'2023-05-04'<l['opened'][:10]<='2023-07-21':continue
  assert l['qty']==0 and l['closed'][:10]<='2023-07-21'
  end=D(l['cash'])+D(l['dividend']);c=cls[str(l['id'])]
  layers.append(dict(layer=l['id'],sid=l['sid'],cohort='NEW_AFTER_PEAK_'+c['classification'],peak_qty=0,peak_mark=Z,peak_lifecycle_wealth=Z,final_closed_lifecycle_wealth=end,drawdown_period_wealth_change=end,root_original_classification=c,terminal_closed_original_layer=l))
 bridge_diff=sum((r['drawdown_period_wealth_change']for r in layers),Z)-D(summ['drawdown']['wealth_change'])
 assert abs(bridge_diff)<D('1e-18')
 cohorts={};by_stock=defaultdict(lambda:defaultdict(lambda:Z))
 for r in layers:
  c=r['cohort'];v=r['drawdown_period_wealth_change']
  if c not in cohorts:cohorts[c]=dict(layers=0,delta=Z,negative_sum=Z,positive_sum=Z)
  a=cohorts[c];a['layers']+=1;a['delta']+=v;a['negative_sum']+=min(Z,v);a['positive_sum']+=max(Z,v)
  by_stock[r['sid']][c]+=v
 for r in dd:assert abs(sum(by_stock[r['sid']].values(),Z)-D(r['stock_wealth_change']))<D('1e-18')
 save('PEAK_EXISTING_VS_NEW_LAYER_BRIDGE.json',dict(peak='2023-05-04 CLOSE',end='2023-07-21 CLOSE',cohorts=cohorts,stock_breakdown=by_stock,layers=layers,sum_delta=sum((r['drawdown_period_wealth_change']for r in layers),Z),residual=bridge_diff,definitions='Existing positive means saved layer cash+dividend+current mark was positive at5/4, not future winner selection; new roles use shared actual quantity classes; closed lifecycle numbers are separate from annual contributions.'))
 save('SHARED_CROSSCHECK_AND_SOURCE_SHA256.json',dict(all_2023_stock_annual_contributions_match_root_layer_table_within_1e_minus18_CNY=True,maximum_shared_stock_difference=max(map(abs,stock_diffs.values())),selected_buy_classifications_and_quantities_match_root=True,selected_cycle_ids_use_root=True,peak_drawdown_layer_stock_account_bridges_within_1e_minus18_CNY=True,peak_bridge_residual=bridge_diff,sha256=H))
if __name__=='__main__':main()
