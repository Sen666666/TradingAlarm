from audit import *
from collections import Counter

def dm(p):return {(r['account'],r['at']):r for r in rows(p)}

def verify():
 ncontrol=0;nprefix=0;nnew=0;audits=[];concentration=[];meta=pd.read_csv(C.DESIGN/'proposed-pool.csv').set_index('symbol')
 for v in ['RS','PVR']:
  a=dm(O/v/'technical/control/daily.jsonl.gz');b=dm(PRIOR/v/'accounts-v2/daily.jsonl.gz');assert a.keys()==b.keys()
  for k,r in a.items():
   for f in FIELDS:assert r[f]==b[k][f],(v,k,f)
   ncontrol+=1
  for sc in ['base','cost2','delay1']:
   aid='I__S0_'+sc;assert read(O/v/'technical/control'/f'{aid}.json')['fills']==read(PRIOR/v/'accounts-v2'/f'{aid}.json')['fills']
  audits.append(read(O/v/'technical/control-analysis/accounting.json'))
 for v in ['RS_NC','PVR_NC']:
  audit=read(O/v/'analysis/accounting.json');assert audit['passed'];audits.append(audit);nnew+=audit['daily_rows']
  full=dm(O/v/'accounts-v2/daily.jsonl.gz');pre=dm(O/v/'technical/prefix/daily.jsonl.gz');expected={k:r for k,r in full.items() if k[1][:10]<='2026-06-30'};assert pre.keys()==expected.keys()
  for k,r in pre.items():
   for f in FIELDS:assert r[f]==expected[k][f],(v,k,f)
   nprefix+=1
  dec={(r['account'],r['at']):r for r in rows(O/v/'accounts-v2/decisions.jsonl.gz')}
  for r in rows(O/v/'technical/prefix/decisions.jsonl.gz'):assert r==dec[r['account'],r['at']]
  for sc in ['base','cost2','delay1']:
   aid='I__S0_'+sc;obj=read(O/v/'accounts-v2'/f'{aid}.json');assert read(O/v/'technical/prefix'/f'{aid}.json')['fills']==[f for f in obj['fills'] if f['at'][:10]<='2026-06-30'];assert not any(x['kind']=='rotation_started' for x in obj['audit_log'])
 for v in ['RS','PVR','RS_NC','PVR_NC']:
  root=PRIOR/v if v in ['RS','PVR'] else O/v
  daily=dm(root/'accounts-v2/daily.jsonl.gz')
  for sc in ['base','cost2','delay1']:
   part=[r for (aid,t),r in daily.items() if aid=='I__S0_'+sc];peak_s=0;peak_n=0;more3=0;more2=0
   for r in part:
    held=r['positions'];count=Counter(meta.loc[s,'sector_id'] for s in held);peak_s=max(peak_s,len(count));peak_n=max(peak_n,max(count.values(),default=0));more3+=len(count)>3;more2+=max(count.values(),default=0)>2;assert len(held)<=6
    occupied=set(held)|set(r['pending_buys'])|set(r['pending_sells']);assert len(occupied)<=6
   concentration.append({'version':v,'scenario':sc,'max_held_sectors':peak_s,'max_stocks_same_sector':peak_n,'days_more_than_3_sectors':more3,'days_more_than_2_same_sector':more2})
 for path,h in read(O/'freeze.json')['sha256'].items():assert sha(path)==h,path
 for path,h in read(PRIOR/'freeze.json')['sha256'].items():assert sha(path)==h,path
 for x in pd.read_csv(PRIOR/'coverage.csv').to_dict('records'):assert sha(PRIOR/'scores'/f"{x['symbol']}.parquet")==x['score_sha256']
 pd.DataFrame(concentration).to_csv(O/'concentration.csv',index=False)
 save(O/'verification.json',{'passed':True,'exact_control_daily_rows':ncontrol,'exact_control_fills':True,'new_daily_rows':nnew,'physical_prefix_daily_rows':nprefix,'new_paths':6,'economic_reruns':0,'parameter_revisions_after_results':0,'max_nav_error_cny':str(max(D(a['max_nav_difference']) for a in audits)),'audits':audits})

def collect():
 outputs={k:[] for k in ['summary','curves','annual','stocks','campaigns','contributions']};risks=[];daily={};decisions={};riskstate={};slip=[]
 for v in ['RS','PVR','RS_NC','PVR_NC']:
  root=PRIOR/v if v in ['RS','PVR'] else O/v
  for k,into in outputs.items():
   f=pd.read_csv(root/'analysis'/f'{k}.csv');f.insert(0,'version',v);into.append(f)
  daily[v]=dm(root/'accounts-v2/daily.jsonl.gz');decisions[v]={(r['account'],r['at']):r for r in rows(root/'accounts-v2/decisions.jsonl.gz')}
  for sc in ['base','cost2','delay1']:
   aid='I__S0_'+sc;obj=read(root/'accounts-v2'/f'{aid}.json');cost=D(0);riskstate[v,sc]={}
   for r in obj['audit_log']:
    if r['kind']=='risk_checkpoint':
     riskstate[v,sc][r['at'][:10]]=r
     if r['event']:risks.append({'version':v,'scenario':sc,**r})
    if r['kind']=='fill':cost+=abs(D(r['price'])-D(r['raw_open']))*r['receipt']['shares']
   slip.append({'version':v,'scenario':sc,'slippage_cny':float(cost)})
 for k,frames in outputs.items():pd.concat(frames,ignore_index=True).to_csv(O/f'{k}.csv',index=False)
 pd.DataFrame(risks).to_csv(O/'risk-events.csv',index=False);pd.DataFrame(slip).to_csv(O/'slippage.csv',index=False)
 campaigns=pd.read_csv(O/'campaigns.csv');base=campaigns[(campaigns.version=='RS')&(campaigns.scenario=='base')&campaigns.tail_closed];participation=[]
 for _,c in base.iterrows():
  start,end=c.entry_at[:10],c.exit_at[:10]
  for v in ['RS','PVR','RS_NC','PVR_NC']:
   ds=[r for (aid,t),r in daily[v].items() if aid=='I__S0_base' and start<=t[:10]<end];n=sum(r['positions'].get(c.symbol,0)>0 for r in ds)
   participation.append({'version':v,'symbol':c.symbol,'name':c['name'],'original_entry':start,'original_exit':end,'original_profit':c.net_pnl,'observation_days':len(ds),'holding_days':n,'fraction':n/len(ds) if ds else None})
 pd.DataFrame(participation).to_csv(O/'winner-participation.csv',index=False)
 meta=pd.read_csv(C.DESIGN/'proposed-pool.csv').set_index('symbol');trace=[];changes=[]
 for v in ['RS','PVR','RS_NC','PVR_NC']:
  for day,ids in [('2025-06-27',['300502.SZ']),('2025-10-20',['688498.SH','688048.SH'])]:
   key=next(k for k in daily[v] if k[0]=='I__S0_base' and k[1][:10]==day);r=daily[v][key];d=decisions[v][key];occ=set(r['positions'])|set(r['pending_buys'])|set(r['pending_sells']);cnt=Counter(meta.loc[s,'industry'] for s in occ)
   for sid in ids:trace.append({'version':v,'date':day,'symbol':sid,'name':meta.loc[sid,'name'],'account_on':riskstate[v,'base'][day]['on'],'eligible':sid in d['eligible'],'accepted':sid in d['accepted'],'already_committed':sid in occ,'occupied_count':len(occ),'sector_counts':json.dumps(dict(cnt),ensure_ascii=False),'holdings':'|'.join(str(meta.loc[s,'name']) for s in r['positions'])})
 for old,new in [('RS','RS_NC'),('PVR','PVR_NC')]:
  for sc in ['base','cost2','delay1']:
   for k,a in decisions[old].items():
    if k[0]!='I__S0_'+sc:continue
    b=decisions[new][k]
    if a['accepted']!=b['accepted']:
     changes.append({'baseline':old,'new':new,'scenario':sc,'date':k[1][:10],'same_eligible':set(a['eligible'])==set(b['eligible']),'old_accepted':'|'.join(a['accepted']),'new_accepted':'|'.join(b['accepted'])});break
 pd.DataFrame(trace).to_csv(O/'opportunity-traces.csv',index=False);pd.DataFrame(changes).to_csv(O/'first-divergence.csv',index=False)
 stocks=pd.read_csv(O/'stocks.csv');p=stocks.pivot_table(index=['scenario','symbol','name','industry'],columns='version',values='net_profit',aggfunc='sum',fill_value=0).reset_index();p['RS_NC_minus_RS']=p.RS_NC-p.RS;p['PVR_NC_minus_PVR']=p.PVR_NC-p.PVR;p.to_csv(O/'stock-attribution.csv',index=False)
 curves=pd.read_csv(O/'curves.csv');stages=[]
 for (v,sc),g in curves.groupby(['version','scenario']):
  g=g.set_index('date');base=float(g.loc['2026-06-30','nav']);stages.append({'version':v,'scenario':sc,'H2_return':float(g.nav.iloc[-1]/base-1),'H2_profit':float(g.nav.iloc[-1]-base)})
 pd.DataFrame(stages).to_csv(O/'stages.csv',index=False);plot(curves)
 print(pd.read_csv(O/'summary.csv')[['version','scenario','net_return','max_drawdown','mean_exposure','fees','closed','tail_count','tail_profit','ordinary_profit','open_profit','maximum_sector_weight']].to_string(index=False));print('winner holdings',pd.DataFrame(participation).groupby('version').holding_days.sum().to_dict());print('concentration',pd.read_csv(O/'concentration.csv').to_string(index=False));print('traces',pd.DataFrame(trace).to_string(index=False))

def plot(curves):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 fig,ax=plt.subplots(3,2,figsize=(15,10),sharex='col')
 for j,(old,new) in enumerate([('RS','RS_NC'),('PVR','PVR_NC')]):
  for v,label,color in [(old,'原行业配额','#376da9'),(new,'取消行业配额','#d07629')]:
   f=curves[(curves.version==v)&(curves.scenario=='base')];x=pd.to_datetime(f.date);ax[0,j].plot(x,f.nav/1e6,label=label,color=color);ax[1,j].plot(x,100*f.drawdown,color=color);ax[2,j].plot(x,100*f.market_value/f.nav,color=color)
  ax[0,j].set_title('原ACT / RS排序' if old=='RS' else '仅PVR排序');ax[0,j].legend();ax[0,j].set_ylabel('净值，初始=1');ax[1,j].set_ylabel('全历史回撤 %');ax[2,j].set_ylabel('股票仓位 %')
 fig.suptitle('只取消行业配额，最多6股，不加换仓 / 2024—2026-10-27 / 净成本后');fig.tight_layout();fig.savefig(O/'comparison.png',dpi=125);plt.close(fig)

if __name__=='__main__':verify();collect()
