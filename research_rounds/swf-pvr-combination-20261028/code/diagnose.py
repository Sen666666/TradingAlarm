from finish import *
def main():
 s=pd.read_csv(O/'summary.csv');d=pd.read_csv(O/'stock-contributions.csv');out=[]
 for mode in ['SW3F','SW10F']:
  for c in STARTS:
   for scenario in ['base','delay1']+(['cost2'] if c=='S0' else []):
    a=d[(d.strategy=='PVR-'+mode)&(d.cohort==c)&(d.account==mode+'__S0_'+scenario)].set_index('symbol').net
    for ref in ['RS-ACT','RS-SF','PVR-SF','RS-'+mode]:
     rank,policy=ref.split('-');b=d[(d.strategy==ref)&(d.cohort==c)&(d.account==policy+'__S0_'+scenario)].set_index('symbol').net;delta=a.subtract(b,fill_value=0)
     ss=s[(s.cohort==c)&(s.scenario==scenario)].set_index('strategy');assert abs(delta.sum()-(ss.loc['PVR-'+mode,'net_profit']-ss.loc[ref,'net_profit']))<.01
     for sid,v in delta.items():out.append(dict(candidate='PVR-'+mode,reference=ref,cohort=c,scenario=scenario,symbol=sid,delta=v,candidate_net=a.get(sid,0),reference_net=b.get(sid,0)))
 pd.DataFrame(out).to_csv(O/'paired-contributions.csv',index=False);save(O/'attribution-verification.json',{'passed':True,'comparisons':56})
 # Read actual waiting/inheritance trajectories for final combo in earliest base.
 paths=[]
 for mode in ['SW3F','SW10F']:
  a=read(O/'PVR/S0/accounts-v2'/f'{mode}__S0_base.json')
  for r in a['audit_log']:
   if r['kind'] in ['intent_create','waiting_support_raise','intent_end','waiting_support_inherited','open_support_reject'] and r.get('sid') in ['688498.SH','688048.SH','300502.SZ','300308.SZ']:
    paths.append(dict(mode=mode,**r))
 save(O/'winner-protection-trajectories.json',paths)
if __name__=='__main__':main()
