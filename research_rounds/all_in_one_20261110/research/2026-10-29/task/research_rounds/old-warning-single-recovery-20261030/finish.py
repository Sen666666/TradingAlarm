from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,json,statistics
O=Path(__file__).resolve().parent;P=O.parent/'old-side-exit-all69-20261030';Z=D(0)
cs=list(csv.DictReader((O/'full/C-unit-ledgers.csv').open()));ab=list(csv.DictReader((P/'full/unit-ledgers.csv').open()));ix={(r['cycle_id'],int(r['cost']),r['arm']):r for r in ab+cs};keys=list(dict.fromkeys(r['cycle_id'] for r in cs));pairs=[]
def metric(v):
 return dict(net=sum(v,Z),positive=sum((x for x in v if x>0),Z),negative_loss=-sum((x for x in v if x<0),Z),benefit=sum(x>0 for x in v),harm=sum(x<0 for x in v),equal=sum(x==0 for x in v),minimum=min(v),maximum=max(v))
for key in keys:
 for co in [1,2]:
  a,b,c=[ix[key,co,k] for k in ['A','B','C']];ba=D(b['full_cycle_net'])-D(a['full_cycle_net']);cb=D(c['full_cycle_net'])-D(b['full_cycle_net']);ca=D(c['full_cycle_net'])-D(a['full_cycle_net']);assert ba+cb==ca
  pairs.append(dict(cycle_id=key,symbol=a['symbol'],name=a['name'],cost=co,triggered=a['triggered']=='True',old_group='benefit37' if ba>0 else 'harm20' if ba<0 else 'no_warning12',original_tail30=a['original_tail30']=='True',A_net=D(a['full_cycle_net']),B_net=D(b['full_cycle_net']),C_net=D(c['full_cycle_net']),B_minus_A=ba,C_minus_B=cb,C_minus_A=ca,initial_cost=D(a['initial_actual_cost']),recovery_signal=c['recovery_signal'],recovery_buy_at=c['recovery_buy_at'],recovery_status=c['recovery_status'],recovery_buy_qty=c['recovery_buy_qty'],original_A_qty_at_buy=c['original_A_qty_at_buy'],qty_ratio=c['qty_ratio_to_original_A'],signal_price_change=c['signal_price_change_since_sale'],execution_price_change=c['execution_price_change_since_sale'],new_fees=D(c['recovery_extra_fees']),A_DD=a['max_full_cycle_DD'],B_DD=b['max_full_cycle_DD'],C_DD=c['max_full_cycle_DD']))
with (O/'paired-differences.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
target={'605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'};summ={}
for co in [1,2]:
 g=[x for x in pairs if x['cost']==co];groups={'all69':g,'old_harm20':[x for x in g if x['old_group']=='harm20'],'old_benefit37':[x for x in g if x['old_group']=='benefit37'],'no_warning12':[x for x in g if x['old_group']=='no_warning12'],'original_tail14':[x for x in g if x['original_tail30']],'targets3':[x for x in g if x['cycle_id'] in target]};out={}
 for label,gg in groups.items():
  out[label]=dict(cycles=len(gg),A_net=sum((x['A_net'] for x in gg),Z),B_net=sum((x['B_net'] for x in gg),Z),C_net=sum((x['C_net'] for x in gg),Z),effects={k:metric([x[k] for x in gg]) for k in ['B_minus_A','C_minus_B','C_minus_A']})
 h=out['old_harm20'];h['repair_fraction']=h['effects']['C_minus_B']['net']/-h['effects']['B_minus_A']['net'];h['remaining_gap_A_minus_C']=-h['effects']['C_minus_A']['net'];bg=out['old_benefit37'];bg['returned_avoidance']=-bg['effects']['C_minus_B']['net'];bg['returned_fraction']=bg['returned_avoidance']/bg['effects']['B_minus_A']['net'];bg['remaining_avoidance']=bg['effects']['C_minus_A']['net']
 arms={}
 for arm in ['A','B','C']:
  ar=[ix[key,co,arm] for key in keys];arms[arm]=dict(net=metric([D(x['full_cycle_net']) for x in ar]),fees=sum((D(x['full_fees']) for x in ar),Z),dividend=sum((D(x['dividend']) for x in ar),Z),mean_min_return=statistics.mean(D(x['min_full_cycle_return']) for x in ar),worst_min_return=min(D(x['min_full_cycle_return']) for x in ar),mean_max_DD=statistics.mean(D(x['max_full_cycle_DD']) for x in ar),worst_max_DD=max(D(x['max_full_cycle_DD']) for x in ar),mean_holding_closes=statistics.mean(int(x['holding_close_observations']) for x in ar),unclosed=sum(int(x['final_shares'])>0 for x in ar))
 actual=[ix[key,co,'C'] for key in keys if ix[key,co,'C']['recovery_buy_at']];signals=[ix[key,co,'C'] for key in keys if ix[key,co,'C']['recovery_signal']];ratios=[D(x['qty_ratio_to_original_A']) for x in actual];ep=[D(x['execution_price_change_since_sale']) for x in actual];sp=[D(x['signal_price_change_since_sale']) for x in actual];quant={}
 for field in ['qty_loss_slippage','qty_loss_buy_fee','qty_loss_lot','qty_loss_order_or_capacity']:
  quant[field]=statistics.mean(D(x[field])/D(x['original_A_qty_at_buy']) for x in actual)
 recov=dict(signals=len(signals),bought=len(actual),statuses=dict(Counter(ix[key,co,'C']['recovery_status'] for key in keys)),actual_recovery_leg=metric([x['C_minus_B'] for x in g if x['recovery_buy_at']]),new_fees=sum((D(x['recovery_extra_fees']) for x in signals),Z),shares_less=sum(x<1 for x in ratios),shares_more=sum(x>1 for x in ratios),shares_equal=sum(x==1 for x in ratios),median_share_ratio=statistics.median(ratios),min_share_ratio=min(ratios),max_share_ratio=max(ratios),price_up_at_signal=sum(x>0 for x in sp),price_up_at_execution=sum(x>0 for x in ep),median_signal_price_change=statistics.median(sp),median_execution_price_change=statistics.median(ep),mean_share_fraction_effects=quant)
 summ[str(co)]=dict(groups=out,arms=arms,recovery=recov,largest_remaining_harms=sorted(g,key=lambda x:x['C_minus_A'])[:3],largest_recovery_values=sorted(g,key=lambda x:x['C_minus_B'],reverse=True)[:3],largest_recovery_losses=sorted(g,key=lambda x:x['C_minus_B'])[:3],targets=[x for x in g if x['cycle_id'] in target])
(O/'RESULTS.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2,default=str));print(json.dumps(summ,ensure_ascii=False,default=str),flush=True)
