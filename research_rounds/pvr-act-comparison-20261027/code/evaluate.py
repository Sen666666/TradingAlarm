from experiment import *
from collections import defaultdict
from decimal import Decimal as D

def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def daily_map(p):return {(x['account'],x['at']):x for x in rows(p)}
FIELDS=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']

def technical():
 checks=[]
 for version in ['RS','PVR']:
  audit=read(O/version/'technical/short-analysis/accounting.json');assert audit['passed'];checks.append(audit)
 ds=daily_map(O/'RS/technical/short-v2/daily.jsonl.gz');ref=daily_map(ACT/'ACT20_BREAK/accounts-v2/daily.jsonl.gz')
 for key,r in ds.items():
  for f in FIELDS:assert r[f]==ref[key][f],(key,f,r[f],ref[key][f])
 for scenario in config()['scenarios']:
  aid='I__S0_'+scenario;small=read(O/'RS/technical/short-v2'/f'{aid}.json')['fills'];old=read(ACT/'ACT20_BREAK/accounts-v2'/f'{aid}.json')['fills'];assert small==[f for f in old if f['at'][:10]<='2024-03-29']
 save(O/'technical-checks.json',{'passed':True,'control_exact_daily_rows':len(ds),'control_exact_fills':True,'accounting':checks})

def final():
 cfg=config();summary=[];annual=[];stocks=[];campaigns=[];curves=[];risk=[];selection=[];audits=[];slips=[]
 full={};decisions={}
 for version in cfg['versions']:
  for name,into in [('summary',summary),('annual',annual),('stocks',stocks),('campaigns',campaigns),('curves',curves)]:
   f=pd.read_csv(O/version/'analysis'/f'{name}.csv');f.insert(0,'version',version);into.append(f)
  audits.append(read(O/version/'analysis/accounting.json'))
  full[version]=daily_map(O/version/'accounts-v2/daily.jsonl.gz');decisions[version]={(x['account'],x['at']):x for x in rows(O/version/'accounts-v2/decisions.jsonl.gz')}
  for scenario in cfg['scenarios']:
   aid='I__S0_'+scenario;obj=read(O/version/'accounts-v2'/f'{aid}.json');slippage=D(0)
   for x in obj['audit_log']:
    if x['kind']=='risk_checkpoint' and x['event']:risk.append({'version':version,'scenario':scenario,**x})
    if x['kind']=='fill':slippage+=abs(D(x['price'])-D(x['raw_open']))*D(x['receipt']['shares'])
   slips.append({'version':version,'scenario':scenario,'slippage_cny':float(slippage)})
 for name,fs in [('summary',summary),('annual',annual),('stocks',stocks),('campaigns',campaigns),('curves',curves)]:pd.concat(fs,ignore_index=True).to_csv(O/f'{name}.csv',index=False)
 pd.DataFrame(risk).to_csv(O/'risk-events.csv',index=False);pd.DataFrame(slips).to_csv(O/'slippage.csv',index=False)
 # Compare the original economic prefix at every row, not only final NAV.
 reference=daily_map(ACT/'ACT20_BREAK/accounts-v2/daily.jsonl.gz');n=0
 for key,ref in reference.items():
  r=full['RS'][key]
  for f in FIELDS:assert r[f]==ref[f],(key,f,r[f],ref[f])
  n+=1
 for scenario in cfg['scenarios']:
  aid='I__S0_'+scenario;old=read(ACT/'ACT20_BREAK/accounts-v2'/f'{aid}.json')['fills'];now=read(O/'RS/accounts-v2'/f'{aid}.json')['fills'];assert old==[f for f in now if f['at'][:10]<='2026-10-26']
 # Prefix accounts are actually rerun with physically truncated market inputs.
 pn=0
 for version in cfg['versions']:
  pre=daily_map(O/version/'technical/prefix/daily.jsonl.gz');expected={k:v for k,v in full[version].items() if k[1][:10]<='2025-12-31'};assert pre.keys()==expected.keys()
  for key,x in pre.items():
   for f in FIELDS:assert x[f]==expected[key][f],(version,key,f)
   pn+=1
  for scenario in cfg['scenarios']:
   aid='I__S0_'+scenario;a=read(O/version/'technical/prefix'/f'{aid}.json')['fills'];b=read(O/version/'accounts-v2'/f'{aid}.json')['fills'];assert a==[f for f in b if f['at'][:10]<='2025-12-31']
  predec={(x['account'],x['at']):x for x in rows(O/version/'technical/prefix/decisions.jsonl.gz')}
  for key,x in predec.items():assert x==decisions[version][key]
 for key,a in decisions['RS'].items():
  b=decisions['PVR'][key]
  selection.append({'account':key[0],'date':key[1][:10],'RS_accepted':'|'.join(a['accepted']),'PVR_accepted':'|'.join(b['accepted']),'same_eligible':set(a['eligible'])==set(b['eligible']),'same_accepts':a['accepted']==b['accepted'],'same_positions':full['RS'][key]['positions']==full['PVR'][key]['positions']})
 pd.DataFrame(selection).to_csv(O/'selection-differences.csv',index=False)
 st=pd.read_csv(O/'stocks.csv');p=st.pivot_table(index=['scenario','symbol','name','industry'],columns='version',values='net_profit',aggfunc='sum',fill_value=0).reset_index();p['PVR_minus_RS']=p.PVR-p.RS;p.sort_values('PVR_minus_RS').to_csv(O/'stock-attribution.csv',index=False)
 s=pd.read_csv(O/'summary.csv');c=pd.read_csv(O/'curves.csv');stages=[]
 for (v,scenario),g in c.groupby(['version','scenario']):
  g=g.set_index('date')
  for label,start,end in [('2026H1','2025-12-31','2026-06-30'),('2026H2','2026-06-30','2026-10-27')]:
   base=float(g.loc[start,'nav']);part=g.loc[start:end];stages.append({'version':v,'scenario':scenario,'stage':label,'return':float(part.nav.iloc[-1]/base-1),'profit':float(part.nav.iloc[-1]-base)})
 pd.DataFrame(stages).to_csv(O/'stages.csv',index=False)
 cov=pd.read_csv(O/'coverage.csv');checks={'passed':True,'original_exact_prefix_daily_rows':n,'original_exact_fills':True,'physical_account_prefix_rows':pn,'accounting_daily_rows':sum(a['daily_rows'] for a in audits),'max_accounting_nav_difference':max(a['max_nav_difference'] for a in audits),'formula_identity':sha(FORM)==read(O/'input.json')['formula_sha256'],'economic_rule_changes_after_results':0,'missing_score_observations_2024':int(cov.missing.sum()),'ranking_eligibility_changed_days':int((~pd.DataFrame(selection).same_eligible).sum()),'audits':audits}
 for path,digest in read(O/'freeze.json')['sha256'].items():assert sha(path)==digest,path
 for path,digest in read(ROOT/'research_rounds/strategy-choice-20261027/SELECTED_STRATEGY.json')['frozen_dependencies'].items():assert sha(path)==digest,path
 assert checks['formula_identity'];save(O/'verification.json',checks)
 plot(c,s)
 print(s[['version','scenario','net_return','max_drawdown','closed','tail_profit','ordinary_profit','open_profit','fees']].to_string(index=False));print('stock contribution differences',p[p.scenario=='base'].sort_values('PVR_minus_RS').to_string(index=False));print('risk events',pd.DataFrame(risk)[['version','scenario','at','event','nav']].to_string(index=False));print('verification',checks['accounting_daily_rows'],pn)

def plot(c,s):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
 for v,color in [('RS','#3b6ea8'),('PVR','#dd762b')]:
  g=c[(c.version==v)&(c.scenario=='base')].copy();x=pd.to_datetime(g.date);axes[0].plot(x,g.nav/1e6,label='原ACT20_BREAK' if v=='RS' else 'ACT20_BREAK＋个股PVR-Q1',color=color);axes[1].plot(x,g.drawdown*100,color=color);axes[2].plot(x,100*g.market_value/g.nav,color=color)
 axes[0].set_ylabel('净值 / 初始100万元');axes[0].legend();axes[1].set_ylabel('全历史回撤 %');axes[2].set_ylabel('股票市值 / 净值 %');axes[0].set_title('2024—2026-10-27：仅替换个股排序，费用与滑点后');fig.tight_layout();fig.savefig(O/'comparison.png',dpi=130);plt.close(fig)

if __name__=='__main__':technical() if sys.argv[1]=='technical' else final()
