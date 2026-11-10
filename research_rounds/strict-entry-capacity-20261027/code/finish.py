from audit import *

def admit():
 for c in STARTS:
  assert read(O/c/'technical/short-analysis/accounting.json')['passed'];assert read(O/c/'control-short.json')['passed']
 assert read(O/'tests.json')['passed']
 assert read(O/'signal-validation.json')['passed'] and read(O/'graph-review.json')['reviewed']
 save(O/'admission.json',{'passed':True,'short_paths':28,'graph_windows':6,'signal_prefixes':814})
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
 ss=[];caps=[];participation=[];contrib=[]
 import csv,collections
 meta={r['symbol']:r for r in csv.DictReader((P.C.DESIGN/'proposed-pool.csv').open())}
 for c,start in STARTS.items():
  root=O/c;s=pd.read_csv(root/'analysis/summary.csv');s['cohort']=c
  first={'S0':'2024-01-02','S1':'2024-07-01','S2':'2025-01-02'}[c];years=(pd.Timestamp('2026-10-27')-pd.Timestamp(first)).days/365.25;s['cagr']=(s.final_nav/1e6)**(1/years)-1;ss.append(s)
  ds=rows(root/'accounts-v2/decisions.jsonl.gz');by={a:[r for r in ds if r['account']==a] for a in s.account};cs=pd.read_csv(root/'analysis/campaigns.csv')
  for aid in s.account:
   mode=aid.split('__')[0];cap=12 if mode.endswith('12') else 6;per=cap//3;obj=read(root/'accounts-v2'/f'{aid}.json');risk={r['at']:r['on'] for r in obj['audit_log'] if r['kind']=='risk_checkpoint'};cnt=collections.Counter();unique=set();last={};ep=0
   for ix,r in enumerate(by[aid]):
    if not risk[r['at']]:cnt['paused_days']+=1;continue
    cnt['active_days']+=1;occ=r['occupancy'];occupied={z['security_id'] for z in occ};held={z['security_id'] for z in occ if z['has_position']};sectors=collections.Counter(z['sector_id'] for z in occ);accepted=set(r['accepted']);elig=set(r['eligible']);cnt['qualified_days']+=len(elig)
    cnt['opportunity_days']+=len((elig-occupied)|accepted);cnt['accepted_days']+=len(accepted)
    for sid in elig-occupied-accepted:
     sec=meta[sid]['sector_id'];reason='total_cap' if len(occupied)>=cap else 'sector_cap' if sectors[sec]>=per else 'industry_cap' if sec not in sectors and len(sectors)>=3 else 'other'
     cnt[reason]+=1
     if reason=='other':continue
     cnt['blocked']+=1;unique.add(sid)
     if last.get(sid)!=ix-1:ep+=1
     last[sid]=ix
   caps.append(dict(cohort=c,account=aid,policy=mode,scenario=aid.split('_')[-1],**cnt,unique_blocked=len(unique),blocked_episodes=ep,blocked_rate=cnt['blocked']/max(1,cnt['opportunity_days']),blocked_per_active_day=cnt['blocked']/max(1,cnt['active_days'])))
   baseaid=aid.replace(mode+'__','A6__',1);base={r['at']:r for r in by[baseaid]};brisk={r['at']:r['on'] for r in read(root/'accounts-v2'/f'{baseaid}.json')['audit_log'] if r['kind']=='risk_checkpoint'};fixed=covered=0
   for r in by[aid]:
    b=base[r['at']]
    if not brisk[b['at']]:continue
    candidates=set(b['eligible'])-{z['security_id'] for z in b['occupancy'] if z['has_position']};ours={z['security_id'] for z in r['occupancy'] if z['has_position']}|set(r['accepted']);fixed+=len(candidates);covered+=len(candidates & ours)
   participation.append(dict(cohort=c,account=aid,fixed_ACT_opportunity_days=fixed,held_or_accepted_days=covered,coverage=covered/max(1,fixed)))
   cc=cs[cs.account==aid];pnl=cc.groupby('symbol').net_pnl.sum().sort_values(ascending=False);positive=pnl[pnl>0].sum()
   contrib.append(dict(cohort=c,account=aid,top_symbol=pnl.index[0] if len(pnl) else '',top_net=float(pnl.iloc[0]) if len(pnl) else 0,top_positive_share=float(pnl.iloc[0]/positive) if positive else 0,top3_positive_share=float(pnl.head(3).clip(lower=0).sum()/positive) if positive else 0))
 all=pd.concat(ss,ignore_index=True);all.to_csv(O/'summary.csv',index=False);cp=pd.DataFrame(caps);cp.to_csv(O/'capacity.csv',index=False);pd.DataFrame(participation).to_csv(O/'fixed-opportunity.csv',index=False);pd.DataFrame(contrib).to_csv(O/'concentration.csv',index=False)
 verdict={}
 for v in MODES[1:]:
  aa=all[(all.policy==v)&(all.scenario=='base')].set_index('cohort');bb=all[(all.policy=='A6')&(all.scenario=='base')].set_index('cohort');ad=all[(all.policy==v)&(all.scenario=='delay1')].set_index('cohort');bd=all[(all.policy=='A6')&(all.scenario=='delay1')].set_index('cohort');ca=cp[(cp.policy==v)&(cp.scenario=='base')].set_index('cohort');cb=cp[(cp.policy=='A6')&(cp.scenario=='base')].set_index('cohort')
  m={'base_median_nav_ratio':float((aa.final_nav/bb.final_nav).median()),'tail_retention':float(aa.tail_profit.sum()/bb.tail_profit.sum()),'exposure_retention':float(aa.mean_exposure.mean()/bb.mean_exposure.mean()),'base_mean_dd_delta':float((aa.max_drawdown-bb.max_drawdown).mean()),'delay_mean_dd_delta':float((ad.max_drawdown-bd.max_drawdown).mean()),'delay_improved':int((ad.final_nav>bd.final_nav).sum()),'blocking_rate_improved':int((ca.blocked_rate<cb.blocked_rate).sum()),'delay_median_nav_ratio':float((ad.final_nav/bd.final_nav).median())}
  m['research_support']=m['base_median_nav_ratio']>=.9 and m['tail_retention']>=.8 and m['exposure_retention']>=.8 and m['base_mean_dd_delta']<=.02 and m['delay_mean_dd_delta']<=.02 and m['delay_improved']>=2 and m['blocking_rate_improved']>=2;verdict[v]=m
 save(O/'evaluation.json',verdict)
 print(all[['cohort','policy','scenario','net_return','max_drawdown','mean_exposure','tail_profit','ordinary_profit','buy_fills']].to_string(index=False));print(verdict)
if __name__=='__main__':
 if sys.argv[1]=='admit':admit()
 elif sys.argv[1]=='prefix':prefixes(sys.argv[2])
 else:evaluate()
