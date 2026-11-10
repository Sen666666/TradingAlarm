from audit import *

def admit():
 for c in STARTS:
  assert read(O/c/'technical/short-analysis/accounting.json')['passed'];assert read(O/c/'control-short.json')['passed']
 assert read(O/'tests.json')['passed']
 assert read(O/'signal-validation.json')['passed'] and read(O/'graph-review.json')['reviewed']
 save(O/'admission.json',{'passed':True,'short_paths':28,'graph_windows':6,'signal_prefixes':814})
 fs=[O/'RULES.txt',O/'admission.json',O/'tests.json',O/'graph-review.json',O/'signal-validation.json',PRIOR/'freeze.json',FREF/'freeze.json',SREF/'freeze.json',FREF/'code/study.py',SREF/'code/prepare.py',*sorted((FREF/'signals').glob('*.parquet')),*sorted((SREF/'signals').glob('*.parquet')),*sorted((O/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py'))]
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
 all=[];details=[];capacity=[];import collections,csv
 meta={r['symbol']:r for r in csv.DictReader((P.C.DESIGN/'proposed-pool.csv').open())}
 for c in STARTS:
  root=O/c;s=pd.read_csv(root/'analysis/summary.csv');s['cohort']=c;years=(pd.Timestamp('2026-10-27')-pd.Timestamp({'S0':'2024-01-02','S1':'2024-07-01','S2':'2025-01-02'}[c])).days/365.25;s['cagr']=(s.final_nav/1e6)**(1/years)-1;all.append(s)
  ds=rows(root/'accounts-v2/decisions.jsonl.gz');cs=pd.read_csv(root/'analysis/campaigns.csv')
  for aid in s.account:
   a=read(root/'accounts-v2'/f'{aid}.json');ff=[r for r in a['audit_log'] if r['kind']=='fast_support_exit'];cc=cs[cs.account==aid];reentries=0;reentrypnl=0
   for _,row in cc.iterrows():
    if any(r['sid']==row.symbol and r['at'][:10]<row.entry_at[:10] for r in ff):reentries+=1;reentrypnl+=row.net_pnl
   details.append(dict(cohort=c,account=aid,fast_exits=len(ff),cycles_after_prior_fast_exit=reentries,net_after_prior_fast_exit=reentrypnl,all_losses=-cc.loc[cc.net_pnl<0,'net_pnl'].sum(),fees=(cc.buy_fees+cc.sell_fees).sum()))
   risk={r['at']:r['on'] for r in a['audit_log'] if r['kind']=='risk_checkpoint'};cnt=collections.Counter()
   for r in ds:
    if r['account']!=aid or not risk[r['at']]:continue
    cnt['active_days']+=1;occ=r['occupancy'];occupied={z['security_id'] for z in occ};sectors=collections.Counter(z['sector_id'] for z in occ);elig=set(r['eligible']);acc=set(r['accepted']);cnt['opportunities']+=len((elig-occupied)|acc)
    for sid in elig-occupied-acc:
     sec=meta[sid]['sector_id'];reason='total_cap' if len(occupied)>=6 else 'sector_cap' if sectors[sec]>=2 else 'industry_cap' if sec not in sectors and len(sectors)>=3 else 'other';cnt[reason]+=1
     if reason!='other':cnt['blocked']+=1
   capacity.append(dict(cohort=c,account=aid,**cnt,blocked_rate=cnt['blocked']/max(1,cnt['opportunities']),blocked_per_active_day=cnt['blocked']/max(1,cnt['active_days'])))
 d=pd.concat(all,ignore_index=True);d.to_csv(O/'summary.csv',index=False);pd.DataFrame(details).to_csv(O/'fast-exit-reentry.csv',index=False);pd.DataFrame(capacity).to_csv(O/'capacity.csv',index=False);v={}
 for ref in ['ACT','S','F']:
  a=d[(d.policy=='SF')&(d.scenario=='base')].set_index('cohort');b=d[(d.policy==ref)&(d.scenario=='base')].set_index('cohort');ad=d[(d.policy=='SF')&(d.scenario=='delay1')].set_index('cohort');bd=d[(d.policy==ref)&(d.scenario=='delay1')].set_index('cohort')
  v[ref]={'base_dd_improved':int((a.max_drawdown<b.max_drawdown).sum()),'base_median_nav_ratio':float((a.final_nav/b.final_nav).median()),'base_tail_retention':float(a.tail_profit.sum()/b.tail_profit.sum()),'exposure_retention':float(a.mean_exposure.mean()/b.mean_exposure.mean()),'delay_median_nav_ratio':float((ad.final_nav/bd.final_nav).median()),'delay_improved':int((ad.final_nav>bd.final_nav).sum()),'base_mean_dd_delta':float((a.max_drawdown-b.max_drawdown).mean()),'delay_mean_dd_delta':float((ad.max_drawdown-bd.max_drawdown).mean())}
 m=v['S'];r=v['ACT'];passed=m['base_dd_improved']>=2 and m['base_median_nav_ratio']>=.9 and m['base_tail_retention']>=.8 and m['delay_median_nav_ratio']>=.9 and m['exposure_retention']>=.8 and r['delay_improved']>=2 and r['base_mean_dd_delta']<=.02 and r['delay_mean_dd_delta']<=.02
 save(O/'evaluation.json',{'comparisons':v,'research_support':bool(passed)});print(d[['cohort','policy','scenario','net_return','max_drawdown','tail_profit','ordinary_profit','buy_fills']].to_string(index=False));print(v,passed)
if __name__=='__main__':
 if sys.argv[1]=='admit':admit()
 elif sys.argv[1]=='prefix':prefixes(sys.argv[2])
 else:evaluate()
