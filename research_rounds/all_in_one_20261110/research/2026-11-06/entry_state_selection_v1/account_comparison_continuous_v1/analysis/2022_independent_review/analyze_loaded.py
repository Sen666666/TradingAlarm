# Run only in the read-only checkpoint inspection process with x/A/ds/prices already loaded.
# No Account or Runner construction, no inputs/context loader, no strategy execution.
import ast,csv
OUT=P/'analysis/2022_independent_review'
flows=defaultdict(lambda:defaultdict(lambda:D(0)))
for t in A['trades']:
 flows[str(t['at'])[:10]][t['security_id']]+=(t['gross_cny'] if t['side']=='sell' else -t['gross_cny'])-t['fees_cny']
for r in A['audit_log']:
 if r['kind']=='dividend_accrual':
  v=r['receivable'];flows[str(v.ex_at)[:10]][v.security_id]+=v.net_local
path=[];contrib=[];prev={};lastday=None;prevnav=D(1200000)
for r in ds:
 day=str(r['at'])[:10];cur={s:q*prices[s,day] for s,q in r['positions'].items()}
 pn={s:cur.get(s,D(0))-prev.get(s,D(0))+flows[day].get(s,D(0)) for s in set(cur)|set(prev)|set(flows[day])}
 delta=sum(pn.values());assert abs(delta-(r['nav']-prevnav))<D('1e-8'),(day,delta,r['nav']-prevnav)
 downside=[s for s in prev if prices[s,day]<prices[s,lastday]] if lastday else []
 weights=sorted(cur.items(),key=lambda kv:-kv[1])
 path.append(dict(day=day,nav=r['nav'],pnl=delta,stock_count=len(cur),inventory=r['inventory'],exposure=r['inventory']/r['nav'],max_stock=weights[0][0] if weights else None,max_weight=weights[0][1]/r['nav'] if weights else D(0),prior_stocks=len(prev),prior_stocks_price_down=len(downside),prior_down_weight=sum(prev[s] for s in downside)/sum(prev.values()) if prev else D(0),negative_contributors=sum(v<0 for v in pn.values()),worst_stock=min(pn,key=pn.get) if pn else None,worst_stock_pnl=min(pn.values()) if pn else D(0)))
 contrib.extend(dict(day=day,sid=s,pnl=v) for s,v in pn.items());prev=cur;lastday=day;prevnav=r['nav']
print('WORST_DAYS',sorted(path,key=lambda r:r['pnl'])[:5],flush=True)
pd.DataFrame(path).to_csv(OUT/'DAILY_ACCOUNT.csv',index=False);pd.DataFrame(contrib).to_csv(OUT/'DAILY_STOCK_PNL.csv',index=False)
rr=list(csv.DictReader((P/'analysis/2022_loss_attribution/STOCK_ROUNDS_2022.csv').open()))
rounds=[dict(r,pnl=D(r['pnl']),layer_ids=ast.literal_eval(r['layer_ids'])) for r in rr if r['account']=='PVR']
layers={l['id']:l for l in A['layers']}
for r in rounds:
 calc=sum((layers[i]['cash']+layers[i]['dividend']+layers[i]['qty']*prices[r['sid'],'2022-12-30'] for i in r['layer_ids']),D(0))
 assert abs(calc-r['pnl'])<D('1e-8'),('round PNL',r['id'])
closed=[r for r in rounds if r['closed']]
print('ROUND_BRIDGE',sum((r['pnl'] for r in rounds if r['pnl']>0),D(0)),sum((r['pnl'] for r in rounds if r['pnl']<0),D(0)),sum(r['pnl'] for r in rounds),flush=True)
# Fee helper has only immutable rule/protocol metadata; no market data construction.
fm=C.J.M.E.FastMarket.__new__(C.J.M.E.FastMarket)
fm.cache_at=None
fm.rules=json.loads((C.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
fm.protocol=json.loads((C.J.M.BP.C.OLD/'inputs-v2/economic-protocol.json').read_text())
# Reconstruct per-stock moving-average remaining cost from saved actual fills, independently of layers.
ev=[]
for i,t in enumerate(A['trades']):ev.append((t['at'],1,i,'trade',t))
for i,t in enumerate(A['journal']):
 if t['kind']=='actual_split':ev.append((t['at'],0,i,'split',t))
for i,r in enumerate(ds):ev.append((r['at'],2,i,'close',r))
active={};observations=[];closed_events=[];seq=Counter();split_adjustments=[]
for at,_,idx,kind,t in sorted(ev,key=lambda e:e[:3]):
 if kind=='split':
  sid=t['sid']
  if sid in active:
   z=active[sid];before=z['Q'];z['Q']=int(D(before)*D(str(t['ratio'])));split_adjustments.append((sid,str(at),before,z['Q']))
 elif kind=='trade':
  sid=t['security_id'];q=t['shares']
  if t['side']=='buy':
   if sid not in active:
    seq[sid]+=1;active[sid]=dict(sid=sid,opened=str(at),seq=seq[sid],Q=0,K=D(0),cash=D(0),buy_paid=D(0),layer_ids=[],exit_reasons=set())
   z=active[sid];paid=t['gross_cny']+t['fees_cny'];z['Q']+=q;z['K']+=paid;z['cash']-=paid;z['buy_paid']+=paid;z['layer_ids'].append(t['layer'])
  else:
   z=active[sid];z['K']*=D(z['Q']-q)/D(z['Q']);z['Q']-=q;z['cash']+=t['gross_cny']-t['fees_cny'];z['exit_reasons'].update(t['reason'].split(','))
   if z['Q']==0:
    z['closed']=str(at);z['final_exit_reason']=t['reason'];closed_events.append(dict(z));del active[sid]
 else:
  day=str(at)[:10];assert {s:z['Q'] for s,z in active.items()}==t['positions'],('saved quantity',day)
  for sid,z in active.items():
   if sid not in raw:raw[sid]=pd.read_parquet(rawroot/(sid+'.parquet')).set_index('trade_date').sort_index()
   df=raw[sid];d=pd.Timestamp(day);valid=d in df.index and bool(df.loc[d,'observed_bar']) and bool(df.loc[d,'price_eligible']) and not bool(df.loc[d,'synthetic_event_bar'])
   row=dict(sid=sid,opened=z['opened'],day=day,Q=z['Q'],K_remaining=z['K'],buy_paid=z['buy_paid'],cash=z['cash'],valid_actual_close=valid,weight=D(z['Q'])*prices[sid,day]/t['nav'])
   if valid:
    close=D(str(df.loc[d,'close']));sellpx=close*D('.9995');sch=fm.fees(sid,at);par=fm.rules.get('security_metadata',{}).get(sid,{}).get('par_value')
    fee=sum(sch.incremental('sell',D(z['Q'])*sellpx,{}, {},1,shares=z['Q'],par_value=par).values(),D(0))
    u=D(z['Q'])*sellpx-fee-z['K'];div=sum((l['dividend'] for l in t['layers'] if l['id'] in z['layer_ids']),D(0))
    # dividends for already closed layers of same ongoing round are fixed at their actual closure
    liveids={l['id'] for l in t['layers']}
    div+=sum((layers[i]['dividend'] for i in z['layer_ids'] if i not in liveids),D(0))
    row.update(close=close,estimated_sell_fee=fee,U=u,U_over_K=u/z['K'] if z['K']>0 else None,cumulative_round_pnl=z['cash']+D(z['Q'])*close+div)
   observations.append(row)
print('OBS_DONE',len(observations),len(closed_events),flush=True)
assert len(closed_events)==len(closed)
obsmap=defaultdict(list)
for o in observations:obsmap[o['sid'],o['opened']].append(o)
checks=[]
for r in closed:
 ce=next(c for c in closed_events if c['sid']==r['sid'] and c['opened']==r['opened']);assert ce['closed']==r['closed'] and set(ce['layer_ids'])==set(r['layer_ids'])
 assert abs(ce['cash']+sum(layers[i]['dividend'] for i in r['layer_ids'])-r['pnl'])<D('1e-8')
 oo=obsmap[r['sid'],r['opened']];valid=[o for o in oo if o['valid_actual_close']];missing=len(oo)-len(valid)
 best=max(valid,key=lambda o:o['U_over_K']) if valid else None
 if r['pnl']>=0:group='WIN_OR_FLAT'
 elif not valid or missing:group='C_INCOMPLETE_CLOSE_OBSERVATIONS'
 elif max(o['U'] for o in valid)<=0:group='A_NO_POSITIVE_OBSERVED_CLOSE'
 elif best['U_over_K']>=D('.03'):group='B_POSITIVE_AT_LEAST_3PCT'
 else:group='B_POSITIVE_BELOW_3PCT'
 checks.append(dict(**r,group=group,close_observations=len(oo),missing_closes=missing,max_U=max((o['U'] for o in valid),default=None),min_U=min((o['U'] for o in valid),default=None),max_U_over_K=best['U_over_K'] if best else None,max_ratio_day=best['day'] if best else None,max_cumulative_round_pnl=max((o['cumulative_round_pnl'] for o in valid),default=None),max_weight=max((o['weight'] for o in oo),default=None),final_exit_reason=ce['final_exit_reason'],all_exit_reasons='|'.join(sorted(ce['exit_reasons'])),closed_quarter=r['closed'][:4]+'Q'+str((int(r['closed'][5:7])-1)//3+1)))
summary={}
for g in sorted({r['group'] for r in checks}):
 zz=[r for r in checks if r['group']==g];summary[g]=dict(n=len(zz),pnl=sum(r['pnl'] for r in zz))
print('GROUPS',summary,flush=True)
pd.DataFrame(observations).to_csv(OUT/'ROUND_DAILY_CLOSE.csv',index=False);pd.DataFrame(checks).to_csv(OUT/'CLOSED_ROUNDS_MFE.csv',index=False)
(OUT/'SUMMARY.json').write_text(json.dumps(dict(checkpoint_sha256=h,closed_round_groups=summary,account_net=sum(r['pnl'] for r in rounds),daily_net=sum(r['pnl'] for r in path),closed_round_net=sum(r['pnl'] for r in checks),all_round_positive=sum((r['pnl'] for r in rounds if r['pnl']>0),D(0)),all_round_negative=sum((r['pnl'] for r in rounds if r['pnl']<0),D(0)),no_account_run=True),default=str,indent=2))
