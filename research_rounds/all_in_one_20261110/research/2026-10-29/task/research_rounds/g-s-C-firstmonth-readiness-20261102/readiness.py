"""Source coverage and CURRENT obligations only. No account advancement."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import sys,json,pickle,time,copy,hashlib
import pandas as pd,numpy as np,pyarrow.parquet as pq
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-nextsession-native-20261102'));import c_horizon as C
P=C.P;E=C.E;X=C.X
SPECS={'2022':dict(start='2022-01-07',end='2022-01-31'),'2025_26':dict(start='2025-07-04',end='2025-07-31')}
def frame(path,key,cols):
 filters=[[(key,'>=',pd.Timestamp(v['start']).to_pydatetime()),(key,'<=',pd.Timestamp(v['end']).to_pydatetime())] for v in SPECS.values()]
 f=pq.read_table(path,columns=cols,filters=filters).to_pandas()
 if key not in f.columns:f=f.reset_index()
 f[key]=pd.to_datetime(f[key]);return f
def main():
 begun=time.perf_counter();C.guard();inventory=X.LD.read(X.LD.B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json');sources=X.LD.read(P.H.INPUT/'SOURCE_BINDINGS.json');access={}
 def bind(p):
  p=Path(p)
  if str(p) not in access:
   assert P.sha(p)==sources[str(p)],'original source changed '+str(p);access[str(p)]=sources[str(p)]
  return p
 roots=C.read(C.HERE/'CONTINUATION_CHECKPOINTS.json');accounts={}
 for row in roots:
  p=Path(row['path']);assert P.sha(p)==row['sha256']
  with p.open('rb') as f:r=pickle.load(f)
  accounts[row['window']+'-'+row['mode']]=r
 rules=next(iter(accounts.values())).inputs.rules
 days={k:[s[:10] for s in rules['calendars']['A'] if v['start']<=s[:10]<=v['end'] and s[11:16]=='09:30'] for k,v in SPECS.items()}
 data={k:dict(days=days[k],per_day={d:Counter() for d in days[k]},stocks_with_facts=set(),stocks_with_raw=set(),canonical_unknown=[],actions=[],payments=[],held_action_exposure=[]) for k in SPECS}
 names={i['symbol']:i['name'] for i in inventory}
 for n,item in enumerate(inventory):
  sid=item['symbol'];refs=item['refs']
  f=frame(bind(refs['facts']),'date',['date','factor','i_target','e0_ready','i_floor']);cp=frame(bind(refs['CP1']),'date',['date','ready','receipt','candidate']);raw=frame(bind(refs['raw_bars']),'trade_date',['trade_date','open','high','low','close','volume']);pv=frame(bind(refs['PVR']),'day',['day','score'])
  rights=X.LD.read(bind(refs['actions']))['events'] if refs['actions'] else []
  for k,spec in SPECS.items():
   d=data[k];scope=set(d['days'])
   for name,g,col in [('facts',f,'date'),('cp',cp,'date'),('raw',raw,'trade_date'),('pvr',pv,'day')]:
    zz=g[g[col].dt.strftime('%Y-%m-%d').isin(scope)]
    for row in zz.to_dict('records'):
     day=row[col].date().isoformat();d['per_day'][day][name]+=1
     if name=='facts':
      d['stocks_with_facts'].add(sid)
      if not np.isfinite(row['factor']) or row['factor']<=0:d['per_day'][day]['invalid_factor']+=1
     if name=='raw':
      d['stocks_with_raw'].add(sid)
      if row['high']<=row['low']:d['per_day'][day]['raw_flat_proxy']+=1
     if name=='pvr' and not np.isfinite(row['score']):d['per_day'][day]['pvr_NA']+=1
     if name=='cp' and row['receipt']:d['per_day'][day]['CP1_true']+=1
   rr=X.LD.read(bind(refs['receipts_2022' if k=='2022' else 'receipts']))
   for r in rr:
    if r['confirmed_day'] in scope:
     d['per_day'][r['confirmed_day']]['canonical']+=1
     if r['trace_unknown']:d['canonical_unknown'].append(dict(sid=sid,day=r['confirmed_day'],unknown=r['trace_unknown']))
   for ev in rights:
    if ev['effective_date'] in scope:d['actions'].append(dict(sid=sid,name=item['name'],**ev))
    if ev.get('paid_at') and ev['paid_at'][:10] in scope:d['payments'].append(dict(sid=sid,**ev))
  if (n+1)%500==0:print('READ_ONLY_SOURCE',n+1,round(time.perf_counter()-begun,2),flush=True)
 hp=bind(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'));h=np.load(hp,allow_pickle=False);hd=pd.DatetimeIndex(h['dates']);symbols=[str(s) for s in h['symbols']];hc={s:i for i,s in enumerate(symbols)}
 catalogue=X.LD.read(X.LD.B/'industry-coverage/run-v1/NODE_CATALOGUE.json');nodes=[dict(node_id='NATIVE1709_global',input_file=str(X.LD.B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'))]+[n for n in catalogue if n['domain']=='NATIVE1709']
 for node in nodes:
  ff=frame(bind(node['input_file']),'date',['date','price_input','breadth'])
  for row in ff.to_dict('records'):
   day=row['date'].date().isoformat()
   for k,d in data.items():
    if day in d['per_day']:
     d['per_day'][day]['F1']+=1
     if not np.isfinite(row['breadth']):d['per_day'][day]['F1_breadth_unknown']+=1
     if not np.isfinite(row['price_input']):d['per_day'][day]['F1_price_unknown']+=1
 for k,d in data.items():
  sectors=accounts[k+'-C10'].inputs.m['sectors'];ids=accounts[k+'-C10'].inputs.ids
  for day in d['days']:
   ix=hd.get_indexer([pd.Timestamp(day)])[0];assert ix>=0
   d['per_day'][day]['H1_stock_rows']=len(ids);d['per_day'][day]['H1_industry_rows']=len(sectors)
   d['per_day'][day]['H1_stock_NA']=int(np.isnan(h['score'][ix,[hc[s] for s in ids]]).sum());d['per_day'][day]['H1_industry_NA']=int(np.isnan(h['score'][ix,[hc[s] for s in sectors]]).sum())
  for mode in ('C10','C_BATCH20'):
   r=accounts[k+'-'+mode];a=r.account
   for ev in d['actions']:
    sid=ev['sid'];ratio=D(ev['split_ratio']);layers=[z for z in a.layers if z['sid']==sid and z['qty']];locks=[z for z in a.policy.locks.values() if z.sid==sid and z.remaining];candidates=[c for c in r.authority.certificates.values() if c['Q'].get(sid,0)>0 and E.iso(c['deadline'])>=E.iso(ev['effective_date']+'T00:00:00+08:00') and not any(o['cid']==c['certificate_id'] and o['sid']==sid for o in r.authority.orders.values())]
    if layers or locks or candidates or sid in a.buys:
     d['held_action_exposure'].append(dict(mode=mode,sid=sid,name=names[sid],effective_date=ev['effective_date'],ratio=ratio,cash_per_old_share=ev['cash_per_old_share'],paid_at=ev['paid_at'],layers=[dict(layer=z['id'],q=z['qty'],role=a.capital_meta[z['id']]['role']) for z in layers],fractional_current_layers=[z['id'] for z in layers if D(z['qty'])*ratio%1],fractional_current_locks=[z.eid for z in locks if D(z.remaining)*ratio%1],unsubmitted_positive_certificate=[c['certificate_id'] for c in candidates],next_session_before_any_trade=ev['effective_date']==d['days'][0],future_holdings_not_assumed=True))
  d['no_facts_any_in_remaining_month']=sorted(set(ids)-d['stocks_with_facts']);d['no_raw_any_in_remaining_month']=sorted(set(ids)-d['stocks_with_raw']);d['stocks_with_facts']=len(d['stocks_with_facts']);d['stocks_with_raw']=len(d['stocks_with_raw'])
  d['coverage_counts_complete']=all(v['F1']==91 and v['pvr']==1709 and v['H1_industry_rows']==90 and v['canonical']==v['CP1_true'] for v in d['per_day'].values())
 obligations=[]
 for key,r in accounts.items():
  a=r.account;book=json.loads(r.budget.dumps())['body'];obligations.append(dict(arm=key,cursor=str(r.last_completed_event),active_native_buys=len(a.buys),pending_intents=len(a.pending),exits={s:dict(order=o.event_id,remaining_target=o.remaining_target) for s,o in a.exits.items()},carry=book['batch']['carry'],new=book['batch']['new'],budget_responsibility_lines=book['lines'],active_certificate=dict(Q=r.active['Q'],deadline=r.active['deadline']),native_available=a.available,source_unchanged=True))
 E.IO.write_json(HERE/'READINESS.json',dict(scope='read-only complete remaining first-month source inventory, no account advancement',data=data,current_obligations=obligations,source_files_verified=len(access),seconds=time.perf_counter()-begun,models_recomputed=0,financial_events=0),encoder=E.encode)
 E.IO.write_json(HERE/'SOURCE_BINDINGS.json',access);print('COMPLETE',round(time.perf_counter()-begun,2),flush=True)
if __name__=='__main__':main()
