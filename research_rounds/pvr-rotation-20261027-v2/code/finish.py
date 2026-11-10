from audit import *

FIELDS=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']

def dm(p):return {(r['account'],r['at']):r for r in rows(p)}

def verify():
 control_rows=0;prefix_rows=0;full_rows=0;audits=[]
 for v in ['RS','PVR']:
  root=O/v/'technical/control';new=dm(root/'daily.jsonl.gz');old=dm(PREVIOUS/v/'accounts-v2/daily.jsonl.gz');assert new.keys()==old.keys()
  for k,x in new.items():
   for f in FIELDS:assert x[f]==old[k][f],(v,k,f)
   control_rows+=1
  for sc in ['base','cost2','delay1']:
   aid='I__S0_'+sc;assert read(root/f'{aid}.json')['fills']==read(PREVIOUS/v/'accounts-v2'/f'{aid}.json')['fills']
  audits.append(read(O/v/'technical/control-analysis/accounting.json'))
 for v in ['ROT','ROT25']:
  a=read(O/v/'analysis/accounting.json');assert a['passed'];audits.append(a);full_rows+=a['daily_rows'];full=dm(O/v/'accounts-v2/daily.jsonl.gz');pre=dm(O/v/'technical/prefix/daily.jsonl.gz');expected={k:r for k,r in full.items() if k[1][:10]<='2026-06-30'};assert pre.keys()==expected.keys()
  for k,x in pre.items():
   for f in FIELDS:assert x[f]==expected[k][f],(v,k,f)
   prefix_rows+=1
  ds={(r['account'],r['at']):r for r in rows(O/v/'accounts-v2/decisions.jsonl.gz')}
  for x in rows(O/v/'technical/prefix/decisions.jsonl.gz'):assert x==ds[x['account'],x['at']]
  for sc in ['base'] if v=='ROT25' else ['base','cost2','delay1']:
   aid='I__S0_'+sc;assert read(O/v/'technical/prefix'/f'{aid}.json')['fills']==[f for f in read(O/v/'accounts-v2'/f'{aid}.json')['fills'] if f['at'][:10]<='2026-06-30']
 for path,digest in read(O/'freeze.json')['sha256'].items():assert sha(path)==digest,path
 for path,digest in read(PREVIOUS/'freeze.json')['sha256'].items():assert sha(path)==digest,path
 for row in pd.read_csv(PREVIOUS/'coverage.csv').to_dict('records'):
  assert sha(PREVIOUS/'scores'/f"{row['symbol']}.parquet")==row['score_sha256']
 save(O/'verification.json',{'passed':True,'control_exact_daily_rows':control_rows,'control_exact_fills':True,'new_full_daily_rows':full_rows,'new_physical_prefix_daily_rows':prefix_rows,'max_nav_error_cny':str(max(D(a['max_nav_difference']) for a in audits)),'audits':audits,'economic_paths':4,'economic_reruns':1,'strategy_changes_after_results':0,'repair':read(O/'repair.json')})

def collect():
 outputs={k:[] for k in ['summary','curves','annual','stocks','campaigns','contributions']};daily={};risks=[];rotations=[];slips=[]
 for v in ['RS','PVR','ROT','ROT25']:
  root=PREVIOUS/v if v in ['RS','PVR'] else O/v
  for k,into in outputs.items():
   f=pd.read_csv(root/'analysis'/f'{k}.csv');f.insert(0,'version',v);into.append(f)
  daily[v]=dm(root/'accounts-v2/daily.jsonl.gz')
  for sc in ['base'] if v=='ROT25' else ['base','cost2','delay1']:
   aid='I__S0_'+sc;obj=read(root/'accounts-v2'/f'{aid}.json');byid={};paired={};slippage=ZERO
   for x in obj['audit_log']:
    if x['kind']=='risk_checkpoint' and x['event']:risks.append({'version':v,'scenario':sc,**x})
    if x['kind']=='rotation_started':
     z=x['rotation'];r=daily[v][aid,x['at']];sid=z['victim'];raw=Path(read(PREVIOUS/'input.json')['snapshot']['path'])/'signals'/f'{sid}.parquet';f=pd.read_parquet(raw);price=float(f.loc[pd.Timestamp(x['at'][:10]),'raw_close']);weight=r['positions'][sid]*price/float(r['nav'])
     byid[z['id']]={'version':v,'scenario':sc,**z,'status':'open','victim_weight_at_signal':weight,'sold_at':None,'actual_new_buy_fills':0,'actual_new_buy_gross':ZERO}
    if x['kind']=='rotation_buy_reserved':paired[x['order_id']]=x['rotation']['id'];byid[x['rotation']['id']].update(sold_at=x['rotation']['sold_at'],buy_order=x['order_id'])
    if x['kind']=='rotation_finished':byid[x['rotation']['id']].update(**x['rotation'],status=x['reason'])
    if x['kind']=='fill':
     f=x['receipt'];slippage+=abs(D(x['price'])-D(x['raw_open']))*D(f['shares'])
     if f['side']=='buy' and x['order_id'] in paired:
      z=byid[paired[x['order_id']]];z['actual_new_buy_fills']+=1;z['actual_new_buy_gross']+=D(f['gross_cny']);z.setdefault('first_new_buy_at',f['at'])
   rotations+=list(byid.values());slips.append({'version':v,'scenario':sc,'slippage_cny':float(slippage)})
 for k,fs in outputs.items():pd.concat(fs,ignore_index=True).to_csv(O/f'{k}.csv',index=False)
 pd.DataFrame(E.native.encoded(rotations)).to_csv(O/'rotations.csv',index=False);pd.DataFrame(risks).to_csv(O/'risk-events.csv',index=False);pd.DataFrame(slips).to_csv(O/'slippage.csv',index=False)
 funnels=[]
 for v in ['ROT','ROT25']:
  for sc in ['base'] if v=='ROT25' else ['base','cost2','delay1']:
   rs=[r for r in rotations if r['version']==v and r['scenario']==sc]
   funnels.append({'version':v,'scenario':sc,'started':len(rs),'sold':sum(r['sold_at'] is not None for r in rs),'bought':sum(r['actual_new_buy_fills']>0 for r in rs),'sold_no_buy':sum(r['sold_at'] is not None and not r['actual_new_buy_fills'] for r in rs),'not_sold':sum(r['sold_at'] is None for r in rs),'unfinished':sum(r['status']=='open' for r in rs),'victim_above_15pct':sum(r['victim_weight_at_signal']>.15 for r in rs),'statuses':dict(Counter(r['status'] for r in rs))})
 save(O/'rotation-funnel.json',funnels)
 # Participation within every original ACT >=30% completed winning campaign.
 campaigns=pd.read_csv(O/'campaigns.csv');base=campaigns[(campaigns.version=='RS')&(campaigns.scenario=='base')&campaigns.tail_closed];participation=[]
 for _,c in base.iterrows():
  start=c.entry_at[:10];end=c.exit_at[:10]
  for v in ['RS','PVR','ROT','ROT25']:
   ds=[r for (aid,t),r in daily[v].items() if aid=='I__S0_base' and start<=t[:10]<end];n=sum(r['positions'].get(c.symbol,0)>0 for r in ds)
   participation.append({'version':v,'symbol':c.symbol,'name':c['name'],'original_entry':start,'original_exit':end,'original_profit':c.net_pnl,'observed_days':len(ds),'holding_days':n,'fraction':n/len(ds) if ds else None})
 pd.DataFrame(participation).to_csv(O/'original-winner-participation.csv',index=False)
 curves=pd.read_csv(O/'curves.csv');stages=[]
 for (v,sc),f in curves.groupby(['version','scenario']):
  f=f.set_index('date');base=float(f.loc['2026-06-30','nav']);stages.append({'version':v,'scenario':sc,'H2_return':float(f.nav.iloc[-1]/base-1),'H2_profit':float(f.nav.iloc[-1]-base)})
 pd.DataFrame(stages).to_csv(O/'stages.csv',index=False)
 stocks=pd.read_csv(O/'stocks.csv');pivot=stocks.pivot_table(index=['scenario','symbol','name','industry'],columns='version',values='net_profit',aggfunc='sum',fill_value=0).reset_index();pivot['ROT_minus_PVR']=pivot.ROT-pivot.PVR;pivot['ROT_minus_RS']=pivot.ROT-pivot.RS;pivot.to_csv(O/'stock-comparison.csv',index=False)
 plot(curves)
 print(pd.read_csv(O/'summary.csv')[['version','scenario','net_return','max_drawdown','mean_exposure','fees','closed','tail_count','tail_profit','ordinary_profit','open_profit']].to_string(index=False));print('funnels',json.dumps(E.native.encoded(funnels),ensure_ascii=False));print('participation',pd.DataFrame(participation).groupby('version').holding_days.sum().to_dict());print(pivot[pivot.scenario=='base'].sort_values('ROT_minus_PVR')[['symbol','name','RS','PVR','ROT','ROT_minus_PVR']].to_string(index=False))

def plot(curves):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 fig,ax=plt.subplots(3,1,figsize=(13,10),sharex=True)
 for v,label,color in [('RS','原ACT＋RS','#356aab'),('PVR','仅替换PVR','#d47b26'),('ROT','PVR＋15分换仓','#248269')]:
  f=curves[(curves.version==v)&(curves.scenario=='base')];x=pd.to_datetime(f.date);ax[0].plot(x,f.nav/1e6,label=label,color=color);ax[1].plot(x,100*f.drawdown,color=color);ax[2].plot(x,100*f.market_value/f.nav,color=color)
 ax[0].legend();ax[0].set_ylabel('净值（初始=1）');ax[1].set_ylabel('全历史回撤 %');ax[2].set_ylabel('股票仓位 %');ax[0].set_title('同一407科技股 / 2024—2026-10-27 / 净费用与滑点后');fig.tight_layout();fig.savefig(O/'comparison.png',dpi=130);plt.close(fig)

if __name__=='__main__':verify();collect()
