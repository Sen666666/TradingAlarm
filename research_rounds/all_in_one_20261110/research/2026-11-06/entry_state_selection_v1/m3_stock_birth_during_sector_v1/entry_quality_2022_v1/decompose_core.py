"""Fixed initial-layer fee counterfactual and event-path decomposition. NOT a strategy rerun."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;P=O.parent/'lifecycle_v1'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import market_identity_on,version_on
from sector_account import FeeSchedule,FeeComponent
r=pd.read_csv(P/'ROUNDS.csv',float_precision='round_trip');a=pd.read_csv(P/'ACTIONS.csv',float_precision='round_trip');x=pd.read_csv(P/'A_RECEIPT_DISPLACEMENT.csv',float_precision='round_trip')
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'];cache={}
def fee(sid,day,q,px):
 key=(sid,day)
 if key not in cache:
  ident=market_identity_on(rules,sid,day,proxies);v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule']
  cache[key]=(FeeSchedule(v['schedule_id'],tuple(FeeComponent(**z) for z in v['components'])),D(str(rules['security_metadata'][sid]['par_value'])))
 fs,par=cache[key]
 return sum(fs.incremental('sell',D(q)*D(str(px)),{}, {},1,shares=q,par_value=par).values(),D(0))
sells=a[a.side.eq('sell_all')].set_index('round_id');buys=a[a.side.eq('buy_core')].set_index('round_id')
for idx,z in r[r.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].iterrows():
 s=sells.loc[z.round_id];q=int(z.entry_q);sf=fee(z.sid,z.exit_day,q,z.exit_price)
 cost=D(q)*D(str(z.entry_price))+D(str(z.entry_fee));net=D(q)*D(str(z.exit_price))-sf-cost
 r.loc[idx,'core_net']=float(net);r.loc[idx,'core_return']=float(net/cost);r.loc[idx,'core_sell_fee']=float(sf);r.loc[idx,'core_buy_cash']=float(cost);r.loc[idx,'prorata_fee_understatement']=float(sf)-s.fee*q/s.q
r.to_csv(O/'CORE_LAYER_RESULTS.csv',index=False)
def performance(g,pnl,ret):
 w=g[g[pnl].gt(0)];l=g[g[pnl].le(0)]
 return dict(wins=len(w),losses=len(l),win_rate=len(w)/len(g) if len(g) else None,payoff_cny=w[pnl].mean()/-l[pnl].mean() if len(w) and len(l) else None,payoff_returns=w[ret].mean()/-l[ret].mean() if len(w) and len(l) else None,mean_return=g[ret].mean() if len(g) else None)
def stats(g):
 c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
 out=dict(selected=len(g),entered=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),closed=len(c),unknown=int(g.status.str.contains('UNKNOWN').sum()),censored=int(g.status.str.contains('CENSORED').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),full=performance(c,'net_pnl','net_return_on_buy_cash'),core=performance(c,'core_net','core_return'),full_loss_to_core_win=int((c.net_pnl.le(0)&c.core_net.gt(0)).sum()),full_win_to_core_loss=int((c.net_pnl.gt(0)&c.core_net.le(0)).sum()))
 assert out['selected']==sum(out[k] for k in ['closed','unknown','censored','nofill'])
 return out
summary=dict(kind="fixed_entry_exit_core_counterfactual_NOT_core_strategy_rerun",formula="q*final_sell_price-core_independent_sell_fee-q*entry_price-initial_buy_fee",unknown="Original UNKNOWN/CENSORED/NOFILL retained, not rescued to closed",windows={})
flat=[]
for win in ['2022','2024_924','2026H1_SEMI']:
 rr=r[r.window.eq(win)];xx=x[x.window.eq(win)];groups={}
 for name,cmp,field in [('common_A','BOTH_SELECTED','round_id_Aonly'),('blocked_A','A_ONLY_SELECTED','round_id_Aonly'),('replacement_A','UNION_ONLY_SELECTED','round_id_Union')]:
  groups[name]=stats(rr[rr.round_id.isin(xx.loc[xx.comparison.eq(cmp),field])])
 groups['union_B']=stats(rr[rr.arm.eq('A_UNION_B')&rr.event_type.str.startswith('B_')])
 arms={arm:stats(g) for arm,g in rr.groupby('arm')};summary['windows'][win]=dict(arms=arms,groups=groups)
 for typ,dd in list(arms.items())+list(groups.items()):
  out=dict(window=win,scope=typ,**{k:v for k,v in dd.items() if k not in ['full','core']})
  out.update({'full_'+k:v for k,v in dd['full'].items()});out.update({'core_'+k:v for k,v in dd['core'].items()});flat.append(out)
pd.DataFrame(flat).to_csv(O/'PATH_CORE_COMPARISON.csv',index=False)
target={('2022','A_ONLY'):310,('2022','A_UNION_B'):506,('2024_924','A_ONLY'):245,('2024_924','A_UNION_B'):452,('2026H1_SEMI','A_ONLY'):0,('2026H1_SEMI','A_UNION_B'):2}
for (w,arm),v in target.items():assert summary['windows'][w]['arms'][arm]['core']['wins']==v
pc=pd.read_csv(O/'SEALED_PAIRED_COHORT.csv').merge(r[['round_id','core_net','core_return']],on='round_id',validate='one_to_one')
pc['core_label']=np.where(pc.core_net.gt(0),'WIN','LOSS');pc.to_csv(O/'PAIRED_CORE_LABELS.csv',index=False)
ps=[]
for pair,g in pc.groupby('pair_id'):
 n=int(g.core_net.gt(0).sum());wc=g[g.label.eq('WIN')].core_net.item();lc=g[g.label.eq('LOSS')].core_net.item()
 kind='BOTH_WIN' if n==2 else 'BOTH_LOSS' if n==0 else 'ORIENTATION_REVERSED' if wc<=0 and lc>0 else 'SAME_WIN_LOSS'
 ps.append(dict(pair_id=pair,kind=kind))
ps=pd.DataFrame(ps);ps.to_csv(O/'PAIRED_CORE_SENSITIVITY.csv',index=False)
cases=pd.read_csv(O/'SEALED_REPRESENTATIVE_CASES.csv').merge(r[['round_id','core_net','core_return']],on='round_id',validate='one_to_one');cases['core_label']=np.where(cases.core_net.gt(0),'WIN','LOSS');cases.to_csv(O/'CORE_CASES.csv',index=False)
closed=r[r.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];noadd=closed[~closed.added.eq(True)]
summary['qa']=dict(paired_core_sensitivity=ps.kind.value_counts().to_dict(),case_label_changes=int(cases.label.ne(cases.core_label).sum()),noadd_count=len(noadd),noadd_core_full_difference=float((noadd.core_net-noadd.net_pnl).abs().max()),nonproportional_fee_cases=int(closed.prorata_fee_understatement.abs().gt(1e-8).sum()),max_prorata_fee_understatement=float(closed.prorata_fee_understatement.max()))
sources=[Path(__file__),P/'ROUNDS.csv',P/'ACTIONS.csv',P/'A_RECEIPT_DISPLACEMENT.csv',B/'code/sector_account.py',B/'code/market_rules.py',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json']
summary['source_hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(O/'PATH_CORE_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
print(json.dumps(summary['qa'],ensure_ascii=False))
print(cases[['name','label','core_label','net_return_on_buy_cash','core_return']].to_string(index=False))
