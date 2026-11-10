from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import csv,json,statistics,hashlib
O=Path(__file__).resolve().parent;P=O.parent/'old-side-exit-all69-20261030';C=O.parent/'old-warning-single-recovery-20261030';Z=D(0)
def rows(p):return list(csv.DictReader(Path(p).open()))
def num(x,k):return D(x.get(k) or '0')
def metric(v):return dict(net=sum(v,Z),positive=sum((x for x in v if x>0),Z),negative_loss=-sum((x for x in v if x<0),Z),benefit=sum(x>0 for x in v),harm=sum(x<0 for x in v),equal=sum(x==0 for x in v))
def export(name,rr):
 keys=list(dict.fromkeys(k for r in rr for k in r))
 with (O/name).open('w') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rr)
allrows=rows(P/'full/unit-ledgers.csv')+rows(C/'full/C-unit-ledgers.csv')+rows(O/'full/new-unit-ledgers.csv');ix={(r['cycle_id'],r['cost'],r['arm']):r for r in allrows};assert len(ix)==690
keys=list(dict.fromkeys(x['cycle_id'] for x in allrows));pairs=[];comparisons={'D_minus_B':('D','B'),'D_minus_CR':('D','C_R'),'CR_minus_C':('C_R','C'),'D_minus_A':('D','A'),'CR_minus_A':('C_R','A')}
for key in keys:
 for co in ['1','2']:
  rr={a:ix[key,co,a] for a in ['A','B','C','C_R','D']};a=rr['A'];ba=num(rr['B'],'full_cycle_net')-num(a,'full_cycle_net');out=dict(cycle_id=key,cost=co,symbol=a['symbol'],name=a['name'],old_group='harm20' if ba<0 else 'benefit37' if ba>0 else 'no_warning12',original_tail=a['original_tail30']=='True',no_old_C=bool(a['triggered']=='True' and not rr['C']['recovery_signal']))
  for arm,r in rr.items():out[arm+'_net']=num(r,'full_cycle_net')
  for label,(up,dn) in comparisons.items():out[label]=num(rr[up],'full_cycle_net')-num(rr[dn],'full_cycle_net')
  assert out['D_minus_B']-out['D_minus_CR']==num(rr['C_R'],'full_cycle_net')-num(rr['B'],'full_cycle_net')
  for arm in ['C_R','D']:
   r=rr[arm]
   for k in ['new','new_name','signal','new_status','new_buy_at','new_buy_qty','initial_sale_cash','actual_gross_budget','new_buy_spend','spent_fraction_of_sale','final_shares','terminal_inventory','terminal_claim','estimated_terminal_liquidation_fee','estimated_terminal_slippage','max_full_cycle_DD']:out[arm+'_'+k]=r.get(k)
  pairs.append(out)
export('all-five-ledgers.csv',allrows);export('paired-differences.csv',pairs);targets={'605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'};result={}
for co in ['1','2']:
 g=[x for x in pairs if x['cost']==co];groups=dict(all69=g,harm20=[x for x in g if x['old_group']=='harm20'],benefit37=[x for x in g if x['old_group']=='benefit37'],no_C22=[x for x in g if x['no_old_C']],tail14=[x for x in g if x['original_tail']],targets3=[x for x in g if x['cycle_id'] in targets],unknown_D4=[x for x in g if x['D_new_status']=='unknown_R21_no_selection'])
 go={}
 for label,gg in groups.items():go[label]=dict(cycles=len(gg),totals={arm:sum((x[arm+'_net'] for x in gg),Z) for arm in ['A','B','C','C_R','D']},effects={key:metric([x[key] for x in gg]) for key in comparisons})
 arms={}
 for arm in ['A','B','C','C_R','D']:
  ar=[ix[k,co,arm] for k in keys];d=dict(net=metric([num(x,'full_cycle_net') for x in ar]),fees=sum((num(x,'full_fees') for x in ar),Z),claims=sum((num(x,'terminal_claim') for x in ar),Z),mean_min_return=statistics.mean(num(x,'min_full_cycle_return') for x in ar),worst_min_return=min(num(x,'min_full_cycle_return') for x in ar),mean_DD=statistics.mean(num(x,'max_full_cycle_DD') for x in ar),worst_DD=max(num(x,'max_full_cycle_DD') for x in ar),mean_holding_closes=statistics.mean(int(x['holding_close_observations']) for x in ar),terminal_positions=sum(int(x['final_shares'])>0 for x in ar))
  if arm in ['C_R','D']:
   chosen=[x for x in ar if x['signal']];warn=[x for x in ar if x['triggered']=='True'];bought=[x for x in chosen if x['new_buy_at']];totalSale=sum((num(x,'initial_sale_cash') for x in warn),Z);selectedSale=sum((num(x,'initial_sale_cash') for x in chosen),Z);spend=sum((num(x,'new_buy_spend') for x in ar),Z);cap=sum((num(x,'actual_gross_budget') for x in chosen),Z);ratios=[num(x,'spent_fraction_of_sale') for x in bought];lqfee=sum((num(x,'estimated_terminal_liquidation_fee') for x in ar),Z);lqslip=sum((num(x,'estimated_terminal_slippage') for x in ar),Z)
   d.update(statuses=dict(Counter(x['new_status'] for x in ar)),orders=len(chosen),bought=len(bought),failed=len(chosen)-len(bought),new_fees=sum((num(x,'new_fees') for x in ar),Z),sum_S_57=totalSale,sum_S_selected=selectedSale,actual_initial_buy_spend=spend,selected_gross_cap_sum=cap,unused_original_S_at_initial_buy=totalSale-spend,median_spent_fraction_selected=statistics.median(ratios),min_spent_fraction_selected=min(ratios),post_sale_inventory_yuan_observations=sum((num(x,'post_sale_inventory_yuan_observations') for x in warn),Z),post_sale_cash_yuan_observations=sum((num(x,'post_sale_cash_yuan_observations') for x in warn),Z),terminal_inventory=sum((num(x,'terminal_inventory') for x in ar),Z),terminal_estimated_liquidation_fee=lqfee,terminal_estimated_liquidation_slippage=lqslip,estimated_net_liquidation_pnl=sum((num(x,'full_cycle_net') for x in ar),Z)-lqfee-lqslip)
  arms[arm]=d
 conc={}
 for label in ['D_minus_B','D_minus_CR']:
  by=defaultdict(lambda:Z)
  for x in g:
   if x['D_new']:by[x['D_new']]+=x[label]
  conc[label]=sorted(((k,v) for k,v in by.items()),key=lambda x:-x[1])[:5]
 result[co]=dict(groups=go,arms=arms,largest_D_B=sorted(g,key=lambda x:-x['D_minus_B'])[:3],largest_D_CR_harms=sorted(g,key=lambda x:x['D_minus_CR'])[:3],largest_D_CR_benefits=sorted(g,key=lambda x:-x['D_minus_CR'])[:3],concentration_by_new=conc,D_open_subset_vs_B=metric([x['D_minus_B'] for x in g if int(x['D_final_shares'])>0]),D_closed_subset_vs_B=metric([x['D_minus_B'] for x in g if x['D_new_buy_at'] and int(x['D_final_shares'])==0]))
for path,sha in json.loads((O/'EXECUTION_IDENTITY.json').read_text())['sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
assert result['1']['groups']['all69']['totals']['A']==D('2984160.2756603511085')
(O/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
for co,r in result.items():
 print('COST',co)
 for label,g in r['groups'].items():print(label,g['cycles'],{k:str(v['net']) for k,v in g['effects'].items()})
 for arm in ['C_R','D']:print(arm,r['arms'][arm])
 print('Dopen',r['D_open_subset_vs_B'],'Dclosed',r['D_closed_subset_vs_B']);print('topD_B',[(x['name'],x['D_new_name'],str(x['D_minus_B'])) for x in r['largest_D_B']]);print('topD_CR_harm',[(x['name'],x['D_new_name'],str(x['D_minus_CR'])) for x in r['largest_D_CR_harms']])
