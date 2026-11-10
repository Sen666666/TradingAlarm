from audit import *

def admit():
 for c in STARTS:
  assert read(O/c/'technical/short-analysis/accounting.json')['passed'];assert read(O/c/'control-short.json')['passed']
 assert read(O/'tests.json')['passed']
 assert read(O/'signal-validation.json')['passed'] and read(O/'graph-review.json')['reviewed']
 save(O/'admission.json',{'passed':True,'short_paths':35,'graph_windows':6,'signal_prefixes':814})
 fs=[O/'RULES.txt',O/'admission.json',O/'tests.json',O/'graph-review.json',O/'signal-validation.json',PRIOR/'freeze.json',*sorted((O/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py'))]
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(p):sha(p) for p in fs}})

def prefixes(c):
 full=O/c/'accounts-v2';pre=O/c/'technical/prefix';f={(r['account'],r['at']):r for r in rows(full/'daily.jsonl.gz')};ds=rows(pre/'daily.jsonl.gz')
 for r in ds:assert r==f[r['account'],r['at']],(c,r['account'],r['at'])
 ff={(r['account'],r['at']):r for r in rows(full/'decisions.jsonl.gz')};dec=rows(pre/'decisions.jsonl.gz')
 for r in dec:assert r==ff[r['account'],r['at']]
 for p in pre.glob('*__S0_*.json'):
  a=read(p);b=read(full/p.name);assert a['fills']==[r for r in b['fills'] if r['at'][:10]<='2026-06-30']
 save(O/c/'prefix-verification.json',{'passed':True,'daily':len(ds),'decisions':len(dec),'fills_exact':True})

def evaluate():
 ss=[];channel=[];fast=[];cash=[]
 for c,start in STARTS.items():
  root=O/c;s=pd.read_csv(root/'analysis/summary.csv');s['cohort']=c
  # Original report helper assumes 2024 start; explicitly correct display CAGR.
  first={'S0':'2024-01-02','S1':'2024-07-01','S2':'2025-01-02'}[c];years=(pd.Timestamp('2026-10-27')-pd.Timestamp(first)).days/365.25;s['cagr']=(s.final_nav/1e6)**(1/years)-1;ss.append(s)
  cs=pd.read_csv(root/'analysis/campaigns.csv')
  for aid in s.account:
   obj=read(root/'accounts-v2'/f'{aid}.json');cl={r['order_id']:r for r in obj['audit_log'] if r['kind']=='intent_entry_class'};extended=set()
   for r in obj['audit_log']:
    if r['kind']=='fill' and r['receipt']['side']=='buy':
     z=cl[r['order_id']]
     if not z['original']:extended.add((z['sid'],r['receipt']['at']))
    elif r['kind']=='fast_support_exit':fast.append(dict(cohort=c,account=aid,**r))
   cycles=cs[(cs.account==aid)&cs.apply(lambda r:(r.symbol,r.entry_at) in extended,axis=1)];tail=cycles[cycles.tail_closed];ordinary=cycles[~cycles.tail_closed]
   channel.append(dict(cohort=c,account=aid,extra_cycles=len(cycles),net=cycles.net_pnl.sum(),tail=tail.net_pnl.sum(),ordinary=ordinary.net_pnl.sum(),gross_losses=-cycles.loc[cycles.net_pnl<0,'net_pnl'].sum(),fees=(cycles.buy_fees+cycles.sell_fees).sum(),intent_created=sum(r['kind']=='intent_create' for r in obj['audit_log']),fast_exits=sum(r['kind']=='fast_support_exit' for r in obj['audit_log'])))
 all=pd.concat(ss,ignore_index=True);all.to_csv(O/'summary.csv',index=False);pd.DataFrame(channel).to_csv(O/'extra-entry-contribution.csv',index=False);pd.DataFrame(fast).to_csv(O/'fast-exits.csv',index=False)
 verdict={}
 for v in MODES[1:]:
  ref='W10' if v=='W10F' else 'ACT';aa=all[(all.policy==v)&(all.scenario=='base')].set_index('cohort');bb=all[(all.policy==ref)&(all.scenario=='base')].set_index('cohort');ad=all[(all.policy==v)&(all.scenario=='delay1')].set_index('cohort');bd=all[(all.policy==ref)&(all.scenario=='delay1')].set_index('cohort')
  metrics={'reference':ref,'base_median_nav_ratio':float((aa.final_nav/bb.final_nav).median()),'tail_retention':float(aa.tail_profit.sum()/bb.tail_profit.sum()),'base_mean_dd_delta':float((aa.max_drawdown-bb.max_drawdown).mean()),'delay_mean_dd_delta':float((ad.max_drawdown-bd.max_drawdown).mean()),'delay_improved':int((ad.final_nav>bd.final_nav).sum()),'base_dd_improved':int((aa.max_drawdown<bb.max_drawdown).sum()),'delay_median_nav_ratio':float((ad.final_nav/bd.final_nav).median())}
  passed=metrics['base_median_nav_ratio']>=.9 and metrics['tail_retention']>=.8
  if v.startswith('W') and v!='W10F':passed=passed and metrics['delay_improved']>=2 and metrics['base_mean_dd_delta']<=.02 and metrics['delay_mean_dd_delta']<=.02
  else:passed=passed and metrics['base_dd_improved']>=2 and metrics['delay_median_nav_ratio']>=.9
  metrics['research_support']=bool(passed);verdict[v]=metrics
 save(O/'evaluation.json',verdict)
 print(all[['cohort','policy','scenario','net_return','max_drawdown','tail_profit','ordinary_profit','buy_fills']].to_string(index=False));print(verdict)
if __name__=='__main__':
 if sys.argv[1]=='admit':admit()
 elif sys.argv[1]=='prefix':prefixes(sys.argv[2])
 else:evaluate()
