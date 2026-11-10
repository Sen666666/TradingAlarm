"""Read saved ledgers only. No engine/strategy import or replay."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent
START=time.time();H={};QA={};TABLES={};ALL=[];STOCK=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):H[str(p)]=sha(p);return json.loads(Path(p).read_text())
def csv(p):H[str(p)]=sha(p);return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,(pd.Timestamp,)):return str(v.date())
 return v

def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+'\n')
def summ(g):
 p=g.net_pnl;loss=-p[p<0].sum();gain=p[p>0].sum()
 return dict(n=len(g),stocks=g.sid.nunique(),wins=int((p>0).sum()),losses=int((p<0).sum()),zero=int((p==0).sum()),net=p.sum(),profit_amount=gain,loss_amount=loss,net_close_max_median=g.close_max.median(),net_close_max_R_median=g.close_max_R.median(),holding_median=g.holding_sessions.median(),probe_trade=g.probe_trade.sum(),add_trade=g.add_trade.sum(),net80_income=g.net80_income.sum(),fees_included=g.all_fees.sum())
for w in ['2022','2024']:
 E=R/f'independent_channel_joint_economic_v1/economic_{w}';rep=read(E/'COMPARISON_REPORT_RECOVERED.json');seal=read(E/'joint/OUTPUT_HASHES.json');common=set(rep['summary'][0]['common_covered_sids'])
 rr=csv(E/'joint/ROUNDS.csv');aa=csv(E/'joint/ACTIONS.csv');gg=csv(E/'joint/PROFIT_GATES.csv');claims=read(E/'joint/CLAIMS.json');bridges=read(E/'joint/BRIDGES.json');cl=csv(E/'joint/CLAIM_LEDGER.csv')
 for n in ['ROUNDS.csv','ACTIONS.csv','PROFIT_GATES.csv','CLAIMS.json','BRIDGES.json','CLAIM_LEDGER.csv']:assert sha(E/'joint'/n)==seal[n],(w,n,'output seal drift')
 r=rr[(rr.owner_lane=='PRICE')&rr.sid.isin(common)&rr.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].copy();r['window_label']=w
 for k in ['entry_day','exit_day','signal_day']:r[k]=pd.to_datetime(r[k])
 b=aa[aa.side.eq('buy_core')].sort_values(['day','sid','round_id']).copy();b['all_strategy_buy_number']=b.groupby('sid').cumcount()+1;b=b.merge(rr[['round_id','owner_lane']],on='round_id',validate='one_to_one');b=b[b.owner_lane=='PRICE'];b['price_buy_number']=b.groupby('sid').cumcount()+1
 r=r.merge(b[['round_id','price_buy_number','all_strategy_buy_number']],on='round_id',validate='one_to_one');r['participation']=np.where(r.all_strategy_buy_number.eq(1),'FIRST_ALL_STRATEGY',np.where(r.price_buy_number.eq(1),'FIRST_PRICE_AFTER_AB','REPEAT_PRICE'))
 risk=pd.DataFrame(rep['round_risk_holding_diagnostics']);risk=risk[(risk.arm=='joint')&(risk.lane=='PRICE')];r=r.merge(risk[['round_id','holding_sessions']],on='round_id',validate='one_to_one')
 g=gg[gg.round_id.isin(r.round_id)&gg.caller.eq('price_held_close')].copy();g['day']=pd.to_datetime(g.day);assert not g.duplicated(['round_id','day']).any();by=g.groupby('round_id');z=by.agg(close_days=('day','size'),close_max=('net_equity','max'),close_min=('net_equity','min'),positive_close_days=('strictly_positive','sum'));z['close_max_day']=g.loc[by.net_equity.idxmax()].set_index('round_id').day;z['close_min_day']=g.loc[by.net_equity.idxmin()].set_index('round_id').day
 r=r.merge(z,on='round_id',validate='one_to_one');assert (r.profitable_close_days==r.positive_close_days).all();assert (r.close_days+1==r.holding_sessions).all()
 # Original price round has one probe, optional one add, one combined terminal sale.
 roles={}
 for a in rep['normalized_actions']:
  if a['arm']!='joint' or a['lane']!='PRICE':continue
  t=roles.setdefault(a['round_id'],{'PROBE':0.,'ADD':0.})
  t[a['role']]+=float(a['q'])*float(a['price'])*(1 if a['side']=='SELL' else -1)-float(a['fee'])
 r['probe_trade']=r.round_id.map(lambda rid:roles[rid]['PROBE']);r['add_trade']=r.round_id.map(lambda rid:roles[rid]['ADD']);r['net80_income']=r.dividend_net80_total
 assert np.allclose(r.probe_trade+r.add_trade+r.net80_income,r.net_pnl,atol=1e-7)
 r['close_max_R']=r.close_max/r.entry_risk;r['close_min_R']=r.close_min/r.entry_risk;r['close_giveback_to_exit']=r.close_max-r.net_pnl
 r['close_R_bucket']=np.where(r.close_max<=0,'NO_POSITIVE_CLOSE',np.where(r.close_max_R<1,'POSITIVE_LT_1R','GE_1R'))
 r['close_outcome']=np.where(r.close_max<=0,'NEVER_POSITIVE_CLOSE',np.where(r.net_pnl<0,'POSITIVE_CLOSE_FINAL_LOSS','POSITIVE_CLOSE_FINAL_PROFIT'))
 r['final_outcome']=np.where(r.net_pnl>0,'PROFIT',np.where(r.net_pnl<0,'LOSS','ZERO'))
 r['hold_bucket']=pd.cut(r.holding_sessions,[0,5,20,60,np.inf],labels=['1_5','6_20','21_60','61_PLUS']).astype(str);r['signal_quarter']=r.signal_day.dt.to_period('Q').astype(str)
 ad=aa[aa.side.eq('buy_add')].copy();ad['day']=pd.to_datetime(ad.day);r['add_day']=r.round_id.map(ad.set_index('round_id').day);g=g.merge(r[['round_id','add_day','entry_day']],on='round_id',validate='many_to_one');g['stage']=np.where(g.day.lt(g.add_day)|g.add_day.isna(),'PRE_ADD','POST_ADD');g['t1_unsettled_included']=g.day.eq(g.entry_day)|g.day.eq(g.add_day)
 for stage in ['PRE_ADD','POST_ADD']:
  s=g[g.stage.eq(stage)].groupby('round_id').net_equity;r[stage.lower()+'_close_max']=r.round_id.map(s.max());r[stage.lower()+'_close_min']=r.round_id.map(s.min())
 r['close_max_t1_settled_only']=r.round_id.map(g[~g.t1_unsettled_included].groupby('round_id').net_equity.max());r['close_positive_only_unsettled']=r.close_max.gt(0)&~r.close_max_t1_settled_only.gt(0)
 totals=summ(r);QA[w]=dict(common_stocks=len(common),closed=totals,registered_common_PRICE=int(((rr.owner_lane=='PRICE')&rr.sid.isin(common)).sum()),gates=len(g),duplicate_gate_days=0,gates_count_plus_exit_open_equals_saved_inclusive_sessions=True,fee_and_net80_role_reconciliation_max_abs=float(abs(r.probe_trade+r.add_trade+r.net80_income-r.net_pnl).max()),source_output_seals_match=True,unsettled_only_positive_n=int(r.close_positive_only_unsettled.sum()),unsettled_only_positive_net=r.loc[r.close_positive_only_unsettled,'net_pnl'].sum())
 for fields in [['close_outcome'],['close_R_bucket'],['close_R_bucket','final_outcome'],['added'],['participation'],['price_buy_number'],['hold_bucket'],['signal_quarter'],['participation','close_outcome'],['added','close_R_bucket']]:
  out=[]
  for key,x in r.groupby(fields,dropna=False,observed=True):
   key=key if isinstance(key,tuple) else (key,);out.append(dict(zip(fields,key),**summ(x)))
  assert abs(sum(x['net'] for x in out)-r.net_pnl.sum())<1e-7
  TABLES[w+'__'+'__'.join(fields)]=out
 st=[]
 for sid,x in r.groupby('sid'):
  st.append(dict(window=w,sid=sid,name=x['name'].iloc[0],**summ(x)))
 st=pd.DataFrame(st);st['loss_rank']=st.loss_amount.rank(method='first',ascending=False).astype(int);st['net_loss_rank']=st.net.rank(method='first').astype(int);STOCK.append(st)
 con=[]
 for n in [10,20]:
  ids=set(st.nsmallest(n,'net').sid);x=r[r.sid.isin(ids)];con.append(dict(group=f'WORST_NET_{n}_STOCKS',**summ(x),gross_loss_share=summ(x)['loss_amount']/totals['loss_amount'],signed_net_over_window_net=x.net_pnl.sum()/totals['net']))
  ids=set(st.nlargest(n,'loss_amount').sid);x=r[r.sid.isin(ids)];con.append(dict(group=f'GROSS_LOSS_{n}_STOCKS',**summ(x),gross_loss_share=summ(x)['loss_amount']/totals['loss_amount']))
 TABLES[w+'__concentration']=con;ALL.append(r)
 print(w,json.dumps(clean(QA[w]),ensure_ascii=False),flush=True)
 print('CLOSE',json.dumps(clean(TABLES[w+'__close_outcome']),ensure_ascii=False),flush=True)
 print('R',json.dumps(clean(TABLES[w+'__close_R_bucket__final_outcome']),ensure_ascii=False),flush=True)
allr=pd.concat(ALL,ignore_index=True);allr.to_csv(O/'ROUND_CLOSE_ATTRIBUTION.csv',index=False);pd.concat(STOCK).to_csv(O/'STOCK_ATTRIBUTION.csv',index=False)
save('CLOSE_TABLES.json',TABLES);save('CLOSE_QA.json',QA);save('SOURCE_HASHES_STAGE1.json',H)
print('COMPLETE_SECONDS',time.time()-START,flush=True)
