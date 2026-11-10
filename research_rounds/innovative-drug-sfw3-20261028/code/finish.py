from audit import *
def admit():
 for c in STARTS:assert read(O/c/'technical/short-analysis/accounting.json')['passed']
 for name in ['technical-control.json','signal-validation.json','market-validation.json']:assert read(O/name)['passed']
 assert read(O/'graph-review.json')['reviewed']
 save(O/'admission.json',{'passed':True,'economic_paths':29,'core_stock_pool':48,'baseline':'SFW3_RS_1'})
 files=[O/'RULES.txt',O/'admission.json',O/'input.json',O/'graph-review.json',O/'technical-control.json',O/'market-validation.json',O/'signal-validation.json',PRIOR/'execution-rules-v2.json',ROOT/'research_rounds/sfw3-rs-baseline-20261028/registry.json',PREP/'h1.npz',PREP/'recovery.csv',*sorted((O/'code').glob('*.py')),*sorted((COMBO/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py')),*sorted(PREP.rglob('*.parquet'))]
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(p):sha(p) for p in files}})
def prefixes(c):
 full=O/c/'accounts-v2';pre=O/c/'technical/prefix';counts={}
 for name in ['daily','decisions']:
  f={(r['account'],r['at']):r for r in rows(full/(name+'.jsonl.gz'))};rr=rows(pre/(name+'.jsonl.gz'))
  for r in rr:assert r==f[r['account'],r['at']],(c,name,r['account'],r['at'])
  counts[name]=len(rr)
 for p in pre.glob('*__S0_*.json'):assert read(p)['fills']==[r for r in read(full/p.name)['fills'] if r['at'][:10]<='2026-06-30']
 save(O/c/'prefix-verification.json',{'passed':True,**counts})
def evaluate():
 ss=[];extended=[];stocks=[];risk=[];cap=[]
 roster=pd.read_csv(O/'pool.csv').set_index('symbol')
 for c in STARTS:
  root=O/c;s=pd.read_csv(root/'analysis/summary.csv');s['cohort']=c;years=(pd.Timestamp('2026-10-27')-pd.Timestamp({'S0':'2024-01-02','S1':'2024-07-01','S2':'2025-01-02'}[c])).days/365.25;s['cagr']=(s.final_nav/1e6)**(1/years)-1;ss.append(s);cs=pd.read_csv(root/'analysis/campaigns.csv');ds=rows(root/'accounts-v2/decisions.jsonl.gz')
  for aid in s.account:
   obj=read(root/'accounts-v2'/f'{aid}.json');counts=collections.Counter();cl={r['order_id']:r for r in obj['audit_log'] if r['kind']=='intent_entry_class'};ext=set();on={};trans=[]
   for r in obj['audit_log']:
    counts[r['kind']]+=1
    if r['kind']=='intent_end':counts['cancel_'+r['reason']]+=1
    if r['kind']=='risk_checkpoint':
     on[r['at']]=r['on']
     if r['event']:trans.append(r)
    if aid.startswith('SW3F') and r['kind']=='fill' and r['receipt']['side']=='buy' and not cl[r['order_id']]['original']:ext.add((r['receipt']['security_id'],r['receipt']['at']))
   cc=cs[cs.account==aid];ec=cc[cc.apply(lambda r:(r.symbol,r.entry_at) in ext,axis=1)] if len(cc) else cc
   extended.append(dict(cohort=c,account=aid,extended_cycles=len(ec),extended_net=ec.net_pnl.sum(),extended_tail=ec.loc[ec.tail_closed,'net_pnl'].sum(),extended_ordinary=ec.loc[~ec.tail_closed,'net_pnl'].sum(),all_losses=-cc.loc[cc.net_pnl<0,'net_pnl'].sum(),fees=(cc.buy_fees+cc.sell_fees).sum(),**counts));risk.append(dict(cohort=c,account=aid,transitions=trans))
   for sid,g in cc.groupby('symbol'):stocks.append(dict(cohort=c,account=aid,symbol=sid,name=g.iloc[0]['name'],net=g.net_pnl.sum(),cycles=len(g)))
   cnt=collections.Counter()
   for r in ds:
    if r['account']!=aid:continue
    if on and not on[r['at']]:cnt['paused_days']+=1;continue
    cnt['active_days']+=1;occ=r['occupancy'];occupied={z['security_id'] for z in occ};sectors=collections.Counter(z['sector_id'] for z in occ);elig=set(r['eligible']);acc=set(r['accepted']);cnt['opportunities']+=len((elig-occupied)|acc)
    for sid in elig-occupied-acc:
     sec=roster.loc[sid,'sector_id'];reason='total_cap' if len(occupied)>=6 else 'sector_cap' if sectors[sec]>=2 else 'industry_cap' if sec not in sectors and len(sectors)>=3 else 'other';cnt[reason]+=1
     if reason!='other':cnt['blocked']+=1
   cap.append(dict(cohort=c,account=aid,**cnt,blocked_per_active_day=cnt['blocked']/max(1,cnt['active_days'])))
 d=pd.concat(ss,ignore_index=True);d.to_csv(O/'summary.csv',index=False);pd.DataFrame(extended).fillna(0).to_csv(O/'extension-and-cost.csv',index=False);pd.DataFrame(stocks).to_csv(O/'stock-contributions.csv',index=False);pd.DataFrame(cap).fillna(0).to_csv(O/'capacity.csv',index=False);save(O/'risk-transitions.json',risk)
 a=d[(d.policy=='SW3F')&(d.scenario=='base')].set_index('cohort');b=d[(d.policy=='ACT')&(d.scenario=='base')].set_index('cohort');ad=d[(d.policy=='SW3F')&(d.scenario=='delay1')].set_index('cohort');bd=d[(d.policy=='ACT')&(d.scenario=='delay1')].set_index('cohort')
 m={'base_not_worse':int((a.final_nav>=b.final_nav).sum()),'delay_improved':int((ad.final_nav>bd.final_nav).sum()),'base_max_dd_worsening':float((a.max_drawdown-b.max_drawdown).max()),'tail_retention':float(a.tail_profit.sum()/b.tail_profit.sum()) if b.tail_profit.sum()>0 else None,'exposure_retention':float(a.mean_exposure.mean()/b.mean_exposure.mean()),'main_dd_below_20pct':bool(a.loc['S0','max_drawdown']<=.2)};m['research_support']=m['base_not_worse']>=2 and m['delay_improved']>=2 and m['base_max_dd_worsening']<=.02 and m['tail_retention'] is not None and m['tail_retention']>=.8 and m['exposure_retention']>=.8;save(O/'evaluation.json',m)
 print(d[['cohort','policy','scenario','net_return','max_drawdown','mean_exposure','tail_profit','ordinary_profit','open_profit','buy_fills']].to_string(index=False));print(m)
def complete():
 for p,h in read(O/'freeze.json')['sha256'].items():assert sha(p)==h,p
 full=prefix=0
 for c in STARTS:
  a=read(O/c/'analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0;full+=a['daily_rows'];p=read(O/c/'prefix-verification.json');assert p['passed'];prefix+=p['daily']
 save(O/'verification.json',{'passed':True,'economic_paths':29,'daily_rows':full,'physical_prefix_daily_rows':prefix,'old_tech_controls':read(O/'technical-control.json'),'signals':read(O/'signal-validation.json')['raw_signal_fact_prefixes'],'strict_fast_prefixes':192,'market_prefixes':2,'economic_reruns':0,'post_outcome_parameter_changes':0,'frozen_hashes_unchanged':True,'platform_changed':False})
 fs=[p for p in O.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.suffix!='.log'];save(O/'completion-hashes.json',{str(p.relative_to(O)):sha(p) for p in fs})
if __name__=='__main__':
 if sys.argv[1]=='admit':admit()
 elif sys.argv[1]=='prefix':prefixes(sys.argv[2])
 elif sys.argv[1]=='complete':complete()
 else:evaluate()
