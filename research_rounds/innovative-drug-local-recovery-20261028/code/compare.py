from finish import *

def compare():
 new=pd.read_csv(O/'summary.csv');old=pd.read_csv(PARENT/'summary.csv');merged=new.merge(old,on=['cohort','account','policy','scenario'],suffixes=('_local','_broad'),validate='one_to_one');assert len(merged)==29
 for k in ['net_return','max_drawdown','mean_exposure','tail_profit','ordinary_profit','open_profit','fees','buy_fills']:merged[k+'_delta']=merged[k+'_local']-merged[k+'_broad']
 merged.to_csv(O/'paired-summary.csv',index=False)
 a=merged[(merged.policy=='SW3F')&(merged.scenario=='base')];d=merged[(merged.policy=='SW3F')&(merged.scenario=='delay1')]
 metrics={'base_improved':int((a.net_return_delta>0).sum()),'delay_improved':int((d.net_return_delta>0).sum()),'base_mean_dd_delta':float(a.max_drawdown_delta.mean()),'delay_mean_dd_delta':float(d.max_drawdown_delta.mean()),'base_tail_retention':float(a.tail_profit_local.sum()/a.tail_profit_broad.sum()),'exposure_retention':float(a.mean_exposure_local.mean()/a.mean_exposure_broad.mean())}
 metrics['research_support']=metrics['base_improved']>=2 and metrics['delay_improved']>=2 and metrics['base_mean_dd_delta']<=.02 and metrics['delay_mean_dd_delta']<=.02 and metrics['base_tail_retention']>=.8 and metrics['exposure_retention']>=.8;save(O/'recovery-evaluation.json',metrics)
 identities=0;stockdiff=[];paths=[]
 for c in STARTS:
  nd=rows(O/c/'accounts-v2/daily.jsonl.gz');od={(r['account'],r['at']):r for r in rows(PARENT/c/'accounts-v2/daily.jsonl.gz')};nc=pd.read_csv(O/c/'analysis/campaigns.csv');oc=pd.read_csv(PARENT/c/'analysis/campaigns.csv')
  for aid in sorted({r['account'] for r in nd}):
   p=aid.split('__')[0];nr=[r for r in nd if r['account']==aid];ob=read(PARENT/c/'accounts-v2'/f'{aid}.json');nb=read(O/c/'accounts-v2'/f'{aid}.json')
   if p in ['I','BH']:
    for r in nr:assert r==od[r['account'],r['at']];identities+=1
    assert nb['fills']==ob['fills']
   ne=[r for r in nb['audit_log'] if r['kind']=='risk_checkpoint'];oe={r['at']:r for r in ob['audit_log'] if r['kind']=='risk_checkpoint'};different=[r['at'] for r in ne if r['on']!=oe[r['at']]['on']]
   first=next((r['at'] for r in nr if r['positions']!=od[r['account'],r['at']]['positions'] or r['nav']!=od[r['account'],r['at']]['nav']),None)
   paths.append(dict(cohort=c,account=aid,first_risk_state_difference=different[0] if different else None,first_economic_difference=first,different_risk_days=len(different),local_events=[r for r in ne if r['event']],broad_events=[r for r in oe.values() if r['event']]))
   aa=nc[nc.account==aid].groupby('symbol').net_pnl.sum();bb=oc[oc.account==aid].groupby('symbol').net_pnl.sum();delta=aa.subtract(bb,fill_value=0);z=merged[(merged.cohort==c)&(merged.account==aid)].iloc[0];assert abs(delta.sum()-(z.net_profit_local-z.net_profit_broad))<.01
   for sid,v in delta.items():stockdiff.append(dict(cohort=c,account=aid,symbol=sid,delta=v,local=aa.get(sid,0),broad=bb.get(sid,0)))
 pd.DataFrame(stockdiff).to_csv(O/'paired-stock-differences.csv',index=False);save(O/'path-comparison.json',paths);save(O/'no-act-identity.json',{'passed':True,'I_BH_control_paths':6,'daily_rows':identities,'fills_exact':True});save(O/'attribution-verification.json',{'passed':True,'account_differences_reconciled':29})
 print(merged[['cohort','policy','scenario','net_return_broad','net_return_local','max_drawdown_broad','max_drawdown_local']].to_string(index=False));print(metrics)
if __name__=='__main__':compare()
