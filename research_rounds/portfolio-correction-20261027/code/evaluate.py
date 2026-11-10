from study import *
from audit import rows,FIELDS
from itertools import combinations
from collections import defaultdict

def evaluate():
 sums=[];csall=[];curves=[];dsall={};pairrows=[];checks=[];channels=[]
 for cohort in STARTS:
  root=O/cohort;au=read(root/'analysis/accounting.json');assert au['passed'] and D(au['max_nav_difference'])==0;checks.append(au)
  s=pd.read_csv(root/'analysis/summary.csv');s['cohort']=cohort;s['strategy']=s.policy.str[:3];s['seed']=s.policy.str[-1].astype(int);sums.append(s)
  cv=pd.read_csv(root/'analysis/curves.csv');cv['cohort']=cohort;cv['strategy']=cv.policy.str[:3];cv['seed']=cv.policy.str[-1].astype(int);curves.append(cv)
  cs=pd.read_csv(root/'analysis/campaigns.csv');cs['cohort']=cohort;cs['strategy']=cs.policy.str[:3];cs['seed']=cs.policy.str[-1].astype(int);cs['entry_channel']='ordinary';cs['rotation_exit']=False
  ds=rows(root/'accounts-v2/daily.jsonl.gz')
  for r in ds:
   assert len(set(r['positions'])|set(r['pending_buys'])|set(r['pending_sells']))<=6
   dsall.setdefault((cohort,r['account']),[]).append(r)
  for aid in s.account:
   obj=read(root/'accounts-v2'/f'{aid}.json');pairs={};buyorders={};starts={}
   for r in obj['audit_log']:
    if r['kind']=='rotation_started':starts[r['rotation']['id']]=r['rotation'];pairs[r['rotation']['id']]=dict(cohort=cohort,account=aid,**r['rotation'],status='pending',actual_buy=False)
    if r['kind']=='rotation_buy_reserved':
     z=r['rotation'];pairs[z['id']].update(z);buyorders[r['order_id']]=z['id']
     mask=(cs.account==aid)&(cs.symbol==z['victim'])&(pd.to_datetime(cs.exit_at,utc=True)==pd.Timestamp(z['sold_at']));cs.loc[mask,'rotation_exit']=True
    if r['kind']=='rotation_finished':pairs[r['rotation']['id']].update(r['rotation']);pairs[r['rotation']['id']]['status']=r['reason']
    if r['kind']=='fill' and r['receipt']['side']=='buy' and r['order_id'] in buyorders:
     receipt=r['receipt'];z=pairs[buyorders[r['order_id']]];z['actual_buy']=True
     mask=(cs.account==aid)&(cs.symbol==receipt['security_id'])&(pd.to_datetime(cs.first_buy_at,utc=True)==pd.Timestamp(receipt['at']));cs.loc[mask,'entry_channel']='replacement'
   pairrows.extend(pairs.values())
  csall.append(cs)
 summary=pd.concat(sums,ignore_index=True);campaigns=pd.concat(csall,ignore_index=True);curve=pd.concat(curves,ignore_index=True)
 for name,frame in [('summary',summary),('campaigns',campaigns),('curves',curve),('pairs',pd.DataFrame(pairrows))]:frame.to_csv(O/f'{name}.csv',index=False)
 base=summary[summary.strategy=='ACT'].set_index(['cohort','seed','scenario']);paired=[]
 for r in summary.itertuples():
  b=base.loc[r.cohort,r.seed,r.scenario];paired.append(dict(cohort=r.cohort,seed=r.seed,strategy=r.strategy,scenario=r.scenario,nav_ratio=r.final_nav/b.final_nav,return_delta=r.net_return-b.net_return,dd_delta=r.max_drawdown-b.max_drawdown,exposure_ratio=r.mean_exposure/b.mean_exposure if b.mean_exposure else np.nan))
 p=pd.DataFrame(paired);p.to_csv(O/'paired.csv',index=False)
 # Lower-path choice uses only predeclared baseline evaluation, never signals.
 poor=[]
 for cohort in STARTS:
  q=summary[(summary.strategy=='ACT')&(summary.scenario=='base')&(summary.cohort==cohort)].sort_values(['final_nav','seed']);poor.append(dict(cohort=cohort,seed=int(q.iloc[0].seed),baseline_return=float(q.iloc[0].net_return)))
 poor=pd.DataFrame(poor);poor.to_csv(O/'baseline-poor-paths.csv',index=False)
 spread=[]
 for keys,g in summary.groupby(['cohort','strategy','scenario']):spread.append(dict(cohort=keys[0],strategy=keys[1],scenario=keys[2],log_nav_std=float(np.std(np.log(g.final_nav/1e6))),min_return=g.net_return.min(),median_return=g.net_return.median(),max_return=g.net_return.max(),max_dd=g.max_drawdown.max()))
 spread=pd.DataFrame(spread);spread.to_csv(O/'dispersion.csv',index=False);verdict=[]
 for v in ['BUF','COR']:
  b=p[(p.strategy==v)&(p.scenario=='base')];bad=b.merge(poor[['cohort','seed']],on=['cohort','seed']);d=p[(p.strategy==v)&(p.scenario=='delay1')];dbad=d.merge(poor[['cohort','seed']],on=['cohort','seed'])
  old=spread[(spread.strategy=='ACT')&(spread.scenario=='base')].set_index('cohort');new=spread[(spread.strategy==v)&(spread.scenario=='base')].set_index('cohort');oldstd=old.log_nav_std.mean();ratio=new.log_nav_std.mean()/oldstd if oldstd>1e-12 else np.nan;improved=int((new.log_nav_std<old.log_nav_std-1e-12).sum());s0=summary[(summary.strategy=='ACT')&(summary.scenario=='base')];s1=summary[(summary.strategy==v)&(summary.scenario=='base')];tail=s1.tail_profit.sum()/s0.tail_profit.sum();exposure=s1.mean_exposure.mean()/s0.mean_exposure.mean()
  metrics=dict(strategy=v,poor_mean_return_delta=bad.return_delta.mean(),poor_improved=int((bad.return_delta>1e-12).sum()),poor_mean_dd_delta=bad.dd_delta.mean(),dispersion_ratio=ratio,dispersion_cohorts_improved=improved,median_nav_ratio=b.nav_ratio.median(),tail_contribution_ratio=tail,exposure_ratio=exposure,delay_poor_mean_delta=dbad.return_delta.mean(),delay_median_nav_ratio=d.nav_ratio.median(),all_path_improved=int((b.return_delta>1e-12).sum()))
  tests=dict(poor_mean=metrics['poor_mean_return_delta']>=.05,poor_majority=metrics['poor_improved']>=2,poor_dd=metrics['poor_mean_dd_delta']<=1e-12,dispersion=ratio<=.8 and improved>=2,nav_guard=metrics['median_nav_ratio']>=.9,tail_guard=tail>=.8,exposure_guard=exposure>=.8,delay_guard=metrics['delay_poor_mean_delta']>=0 and metrics['delay_median_nav_ratio']>=.9)
  verdict.append(dict(**metrics,criteria=tests,supported=all(tests.values())))
 save(O/'evaluation.json',{'criteria_frozen_in_protocol':True,'small_development_sample_not_statistical_proof':True,'verdicts':verdict})
 # Initial variation and subsequent holdings distance; empty/empty excluded.
 dist=[];initial=[]
 for cohort in STARTS:
  for v in ['ACT','BUF','COR']:
   d={seed:dsall[cohort,f'{v}{seed}__S0_base'] for seed in range(3)}
   for age in [5,21,63,126,252]:
    for a,bseed in combinations(range(3),2):
     x=set(d[a][age-1]['positions']);y=set(d[bseed][age-1]['positions']);dist.append(dict(cohort=cohort,strategy=v,observation=age,seed_a=a,seed_b=bseed,both_flat=not(x|y),distance=1-len(x&y)/len(x|y) if x|y else np.nan))
   for seed in range(3):initial.append(dict(cohort=cohort,strategy=v,seed=seed,day=d[seed][4]['at'][:10],stocks=','.join(sorted(d[seed][4]['positions']))))
 pd.DataFrame(dist).to_csv(O/'holdings-distance.csv',index=False);pd.DataFrame(initial).to_csv(O/'initial-holdings.csv',index=False)
 # Common evaluation interval returns normalized to each path's own prior close.
 common=[]
 for (cohort,aid),ds in dsall.items():
  before=[r for r in ds if r['at'][:10]<'2025-01-02'];base_nav=float(before[-1]['nav']) if before else 1e6
  common.append(dict(cohort=cohort,account=aid,return_2025_onward=float(ds[-1]['nav'])/base_nav-1))
 pd.DataFrame(common).to_csv(O/'common-period.csv',index=False)
 # Retention of each paired ACT path's fixed winner holding windows.
 wins=[]
 for cohort in STARTS:
  for seed in range(3):
   w=campaigns[(campaigns.cohort==cohort)&(campaigns.strategy=='ACT')&(campaigns.seed==seed)&(campaigns.scenario=='base')&campaigns.tail_closed]
   for v in ['ACT','BUF','COR']:
    ds=dsall[cohort,f'{v}{seed}__S0_base'];days=0
    for r in w.itertuples():days+=sum(r.first_buy_at[:10]<=d['at'][:10]<r.exit_at[:10] and r.symbol in d['positions'] for d in ds)
    wins.append(dict(cohort=cohort,seed=seed,strategy=v,baseline_tail_count=len(w),held_stock_days=days))
 pd.DataFrame(wins).to_csv(O/'winner-participation.csv',index=False)
 # Actual replacement entrants: all net losses and tails; no fee double count.
 grouped=[]
 for keys,q in campaigns.groupby(['cohort','strategy','seed','scenario','entry_channel']):
  cl=q[q.closed];grouped.append(dict(cohort=keys[0],strategy=keys[1],seed=keys[2],scenario=keys[3],channel=keys[4],cycles=len(q),net_profit=q.net_pnl.sum(),tail_profit=cl.loc[cl.tail_closed,'net_pnl'].sum(),ordinary_net=cl.loc[~cl.tail_closed,'net_pnl'].sum(),gross_losses=-cl.loc[cl.net_pnl<0,'net_pnl'].sum(),fees=(q.buy_fees+q.sell_fees).sum(),open_profit=q.loc[~q.closed,'net_pnl'].sum()))
 pd.DataFrame(grouped).to_csv(O/'channel-contribution.csv',index=False)
 # Independent baseline identity and initial same-seed identity after full replay.
 ref={(r['account'],r['at']):r for r in rows(PRIOR/'RS/accounts-v2/daily.jsonl.gz')}
 for sc in ['base','cost2','delay1']:
  aid='ACT0__S0_'+sc
  for r in dsall['S0',aid]:
   for k in FIELDS:assert r[k]==ref[aid.replace('ACT0','I'),r['at']][k],(sc,r['at'],k)
  assert read(O/'S0/accounts-v2'/f'{aid}.json')['fills']==read(PRIOR/'RS/accounts-v2'/f'I__S0_{sc}.json')['fills']
 for cohort in STARTS:
  for v in ['BUF','COR']:
   for seed in range(3):
    for sc in (['base','cost2','delay1'] if cohort=='S0' else ['base','delay1']):
     a=dsall[cohort,f'{v}{seed}__S0_{sc}'][:5];b=dsall[cohort,f'ACT{seed}__S0_{sc}'][:5]
     for x,y in zip(a,b):
      for k in FIELDS:assert x[k]==y[k]
 for name in ['sha256','signals']:
  for path,h in read(O/'freeze.json')[name].items():assert sha(path)==h,path
 save(O/'full-verification.json',{'passed':True,'paths':len(summary),'daily_rows':sum(c['daily_rows'] for c in checks),'max_nav_difference':0,'original_ACT0_exact':True,'initial_same_seed_exact':True,'source_identity':True,'economic_reruns':0,'post_result_tuning':0})
 print(json.dumps(verdict,ensure_ascii=False,indent=2));print(spread.to_string(index=False))
if __name__=='__main__':evaluate()
