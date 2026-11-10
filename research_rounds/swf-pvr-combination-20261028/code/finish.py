from audit import *
PAIRS=[(r,c) for r in ['RS','PVR'] for c in STARTS]
def admit():
 for rank,c in PAIRS:
  root=O/rank/c;assert read(root/'technical/short-analysis/accounting.json')['passed'];assert read(root/'control-short.json')['passed']
 for fn in ['tests.json','ranking-adapter-validation.json']:assert read(O/fn)['passed']
 assert read(O/'graph-review.json')['reviewed']
 save(O/'admission.json',{'passed':True,'paths':49,'old_controls':14})
 fs=[O/'RULES.txt',O/'admission.json',O/'tests.json',O/'graph-review.json',O/'ranking-adapter-validation.json',PRIOR/'freeze.json',FREF/'freeze.json',SREF/'freeze.json',SFREF/'freeze.json',P.FORM,*sorted((O/'code').glob('*.py')),*sorted((FREF/'signals').glob('*.parquet')),*sorted((SREF/'signals').glob('*.parquet')),*sorted((PRIOR/'scores').glob('*.parquet')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py'))]
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(p):sha(p) for p in fs}})
def prefixes(c,rank):
 root=O/rank/c;full=root/'accounts-v2';pre=root/'technical/prefix';n={}
 for name in ['daily','decisions']:
  f={(r['account'],r['at']):r for r in rows(full/(name+'.jsonl.gz'))};ds=rows(pre/(name+'.jsonl.gz'))
  for r in ds:assert r==f[r['account'],r['at']],(rank,c,name,r['account'],r['at'])
  n[name]=len(ds)
 for p in pre.glob('*__S0_*.json'):assert read(p)['fills']==[r for r in read(full/p.name)['fills'] if r['at'][:10]<='2026-06-30']
 save(root/'prefix-verification.json',{'passed':True,**n})
def evaluate():
 summaries=[];extra=[];capacity=[];contributions=[]
 import csv
 meta={r['symbol']:r for r in csv.DictReader((P.C.DESIGN/'proposed-pool.csv').open())}
 for rank,c in PAIRS:
  root=O/rank/c;s=pd.read_csv(root/'analysis/summary.csv');s['cohort']=c;s['rank']=rank;s['strategy']=rank+'-'+s.policy
  years=(pd.Timestamp('2026-10-27')-pd.Timestamp({'S0':'2024-01-02','S1':'2024-07-01','S2':'2025-01-02'}[c])).days/365.25;s['cagr']=(s.final_nav/1e6)**(1/years)-1;summaries.append(s)
  cs=pd.read_csv(root/'analysis/campaigns.csv');ds=rows(root/'accounts-v2/decisions.jsonl.gz')
  for aid in s.account:
   a=read(root/'accounts-v2'/f'{aid}.json');strategy=rank+'-'+aid.split('__')[0];classes={r['order_id']:r for r in a['audit_log'] if r['kind']=='intent_entry_class'};extended=set();logs=collections.Counter()
   for r in a['audit_log']:
    logs[r['kind']]+=1
    if r['kind']=='intent_end':logs['cancel_'+r['reason']]+=1
    if r['kind']=='fill' and r['receipt']['side']=='buy' and not classes[r['order_id']]['original']:extended.add((r['receipt']['security_id'],r['receipt']['at']))
   cc=cs[cs.account==aid];ec=cc[cc.apply(lambda r:(r.symbol,r.entry_at) in extended,axis=1)]
   extra.append(dict(rank=rank,cohort=c,account=aid,strategy=strategy,extended_cycles=len(ec),extended_net=ec.net_pnl.sum(),extended_tail=ec.loc[ec.tail_closed,'net_pnl'].sum(),extended_ordinary=ec.loc[~ec.tail_closed,'net_pnl'].sum(),all_losses=-cc.loc[cc.net_pnl<0,'net_pnl'].sum(),fees=(cc.buy_fees+cc.sell_fees).sum(),**logs))
   for sid,g in cc.groupby('symbol'):contributions.append(dict(rank=rank,cohort=c,account=aid,strategy=strategy,symbol=sid,name=g.iloc[0]['name'],net=g.net_pnl.sum()))
   risk={r['at']:r['on'] for r in a['audit_log'] if r['kind']=='risk_checkpoint'};cnt=collections.Counter()
   for r in ds:
    if r['account']!=aid or not risk[r['at']]:continue
    cnt['active_days']+=1;occ=r['occupancy'];occupied={z['security_id'] for z in occ};sects=collections.Counter(z['sector_id'] for z in occ);elig=set(r['eligible']);acc=set(r['accepted']);cnt['opportunities']+=len((elig-occupied)|acc)
    for sid in elig-occupied-acc:
     sec=meta[sid]['sector_id'];reason='total_cap' if len(occupied)>=6 else 'sector_cap' if sects[sec]>=2 else 'industry_cap' if sec not in sects and len(sects)>=3 else 'other';cnt[reason]+=1
     if reason!='other':cnt['blocked']+=1
   capacity.append(dict(rank=rank,cohort=c,account=aid,strategy=strategy,**cnt,blocked_per_active_day=cnt['blocked']/max(1,cnt['active_days'])))
 d=pd.concat(summaries,ignore_index=True);d.to_csv(O/'summary.csv',index=False);pd.DataFrame(extra).fillna(0).to_csv(O/'extension-and-cost.csv',index=False);pd.DataFrame(capacity).fillna(0).to_csv(O/'capacity.csv',index=False);pd.DataFrame(contributions).to_csv(O/'stock-contributions.csv',index=False)
 ev={}
 for candidate in ['PVR-SW3F','PVR-SW10F']:
  ev[candidate]={}
  for ref in ['RS-ACT','RS-SF','PVR-SF',candidate.replace('PVR','RS')]:
   a=d[(d.strategy==candidate)&(d.scenario=='base')].set_index('cohort');b=d[(d.strategy==ref)&(d.scenario=='base')].set_index('cohort');ad=d[(d.strategy==candidate)&(d.scenario=='delay1')].set_index('cohort');bd=d[(d.strategy==ref)&(d.scenario=='delay1')].set_index('cohort')
   ev[candidate][ref]={'base_nav_median_ratio':float((a.final_nav/b.final_nav).median()),'tail_retention':float(a.tail_profit.sum()/b.tail_profit.sum()),'exposure_retention':float(a.mean_exposure.mean()/b.mean_exposure.mean()),'delay_improved':int((ad.final_nav>bd.final_nav).sum()),'base_mean_dd_delta':float((a.max_drawdown-b.max_drawdown).mean()),'delay_mean_dd_delta':float((ad.max_drawdown-bd.max_drawdown).mean())}
  m=ev[candidate]['RS-SF'];ev[candidate]['research_support']=m['base_nav_median_ratio']>=.9 and m['tail_retention']>=.8 and m['exposure_retention']>=.8 and m['delay_improved']>=2 and m['base_mean_dd_delta']<=.02 and m['delay_mean_dd_delta']<=.02 and ev[candidate]['RS-ACT']['delay_improved']>=2
 save(O/'evaluation.json',ev);print(d[['strategy','cohort','scenario','net_return','max_drawdown','tail_profit','ordinary_profit','buy_fills']].to_string(index=False));print(ev)
if __name__=='__main__':
 if sys.argv[1]=='admit':admit()
 elif sys.argv[1]=='prefix':prefixes(sys.argv[2],sys.argv[3])
 else:evaluate()
