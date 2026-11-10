"""Saved complete ledgers only; no account construction or event invocation."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,sys,time,argparse,gzip,hashlib
import august_runtime as A
sys.path.insert(0,str(A.M.HERE));from analyze_short import accounting,grouped
sys.path.insert(0,str(A.M.C.OLD));from verify_saved import check_json
P=A.HERE;E=A.E;Z=D(0)
_saved_cache={}
def save(p,x):A.save(p,x)
def saved_bytes(p):
 p=Path(p)
 if p.exists():return p.read_bytes()
 m=A.read(P/'LOSSLESS_OUTPUT_ARCHIVE.json')['entries'];z=m[str(p.relative_to(P))];q=P/z['archive']
 E.require(A.sha(q)==z['gzip_sha256'],'gzip output changed')
 with gzip.open(q,'rb') as f:b=f.read()
 E.require(hashlib.sha256(b).hexdigest()==z['original_sha256'],'lossless output bytes differ')
 return b
def saved_read(p):
 key=str(p)
 if _saved_cache.get('key')!=key:
  b=saved_bytes(p);_saved_cache.clear();_saved_cache.update(key=key,value=json.loads(b),sha256=hashlib.sha256(b).hexdigest())
 return _saved_cache['value']
def saved_sha(p):
 if _saved_cache.get('key')==str(p):return _saved_cache['sha256']
 return hashlib.sha256(saved_bytes(p)).hexdigest()
# Reuse the exact audited seven-bridge arithmetic; only its file reader accepts
# the separately SHA-verified lossless storage format. No financial module edit.
check_json.__globals__['read']=saved_read
def aggregate(ll,key):
 g=defaultdict(lambda:dict(buy=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z))
 for z in ll:
  r=g[z[key]]
  for dest,src in [('buy','buy_gross'),('realized','realized_trade_PNL'),('unrealized','unrealized_net_buy_cost'),('dividend','booked_dividend_income'),('contribution','total_contribution')]:r[dest]+=D(z[src])
 return dict(g)
def opportunities(x,day,names):
 a=x['account'];mapped=next(z for z in x['mapping'] if z['at'][:10]==day)['stocks'];scopes=a['policy']['scopes'];rows=[]
 for z in mapped:
  if z['stock_Q'] is not True or not z['preliminary'] or not z['CP1_id']:continue
  sec=names[z['sid']]['sector'];g=scopes.get('G',{});s=scopes.get(sec,{})
  use='S' if s.get('permit') and s.get('mature') else 'G' if g.get('permit') else 'T' if s.get('permit') else None
  rows.append(dict(day=day,sid=z['sid'],receipt=z['CP1_id'],sector=sec,G_permit=g.get('permit'),G_context=g.get('context'),S_permit=s.get('permit'),S_mature=s.get('mature'),S_context=s.get('context'),ACT_on=a['policy']['act']['on'],market_permission=bool(use),offered_use=use,permission_scope='G' if use=='G' else sec,offered_context=g.get('context') if use=='G' else s.get('context')))
 return rows
def july_prefix_paths(cp):
 side=A.read(cp.with_suffix('.provenance.json'))['binding'];roots=[cp.parent]
 for key,field in [('month_import','parent'),('horizon_import','checkpoint'),('technical_recovery','parent_checkpoint')]:
  if side.get(key,{}).get(field):roots.append(Path(side[key][field]).parent)
 paths={}
 for root in roots:
  for f in root.glob('2025-07-*-CLOSE.json'):
   if f.name in paths:E.require(A.sha(f)==A.sha(paths[f.name]),'conflicting original July saved close '+f.name)
   paths[f.name]=f
 E.require(len(paths)==23,'missing original July close states, cannot invent history')
 return paths
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cells',nargs='+',default=['C10','C20','C10_R0','C20_R0']);ap.add_argument('--partial',action='store_true');args=ap.parse_args();t=time.perf_counter();out=P/('partial-analysis' if args.partial else 'analysis');out.mkdir(exist_ok=True);identity=A.read(A.IDENTITY);names=A.read(A.M.HERE/'inputs/2025_26/metadata.json');results=[];checks=[]
 for cell in args.cells:
  root=P/'runs'/cell;pr=A.read(root/'PROGRESS.json');final=A.read(Path(pr['checkpoint']).with_suffix('.json'));cut=pr['cursor'][:10]
  if not args.partial:E.require(cut=='2025-08-29' and pr['phase']=='CLOSE','incomplete August cell '+cell)
  initial=A.read(Path(identity['accounts'][cell]['checkpoint']).with_suffix('.json'));ll,ss,pnl=accounting(final);oldll,oldss,oldpnl=accounting(initial)
  st=aggregate(ll,'sid');oldst=aggregate(oldll,'sid');sc=aggregate(ll,'sector');oldsc=aggregate(oldll,'sector')
  stocks=[dict(sid=s,name=names[s]['name'],sector=names[s]['sector'],**r,August_contribution=r['contribution']-oldst.get(s,{}).get('contribution',Z),August_buy=r['buy']-oldst.get(s,{}).get('buy',Z)) for s,r in st.items()];stocks.sort(key=lambda z:z['August_contribution'],reverse=True)
  sectors=[dict(sector=s,**r,August_contribution=r['contribution']-oldsc.get(s,{}).get('contribution',Z),August_buy=r['buy']-oldsc.get(s,{}).get('buy',Z)) for s,r in sc.items()];sectors.sort(key=lambda z:z['August_contribution'],reverse=True)
  daily=[];flows=[];peak=D(initial['account']['balance']['nav']);dd=Z
  global_peak=D(1000000);globaldd=Z
  # Reuse prior audited July close curve; do not recompute old finance.
  july_paths=july_prefix_paths(Path(identity['accounts'][cell]['checkpoint']));opportunity=[];scope_history=[]
  for f in sorted(july_paths.values()):
   x=A.read(f);nav=D(x['account']['balance']['nav']);global_peak=max(global_peak,nav);globaldd=max(globaldd,1-nav/global_peak);opportunity+=opportunities(x,f.name[:10],names);scope_history.append((f.name[:10],x['account']['policy']['scopes']))
  aug_paths={str(f) for f in root.glob('2025-08-*.json')}|{str(f.with_suffix('')) for f in root.glob('2025-08-*.json.gz')}
  for path in map(Path,sorted(aug_paths)):
   if path.stem.split('-')[-1] not in ('ACTION','OPEN','CLOSE'):continue
   phase=path.stem.split('-')[-1];x=saved_read(path);a=x['account'];b=a['balance'];diff=check_json(path);checks.append(dict(cell=cell,file=str(path),original_sha256=saved_sha(path),differences=diff));E.require(all(D(v)==0 for v in diff.values()),'saved financial bridge failed '+str(path))
   f=A.read(path.with_name(path.stem+'-FLOW.json'));flows.append(dict(day=path.name[:10],phase=phase,seconds=f['seconds'],fills=len(f['new_fills']),memo_hits=f['memo_hits'],memo_misses=f['memo_misses']))
   if phase!='CLOSE':continue
   nav=D(b['nav']);peak=max(peak,nav);dd=max(dd,1-nav/peak);global_peak=max(global_peak,nav);globaldd=max(globaldd,1-nav/global_peak)
   caps=defaultdict(lambda:Z);stockcaps=defaultdict(lambda:Z);rp=defaultdict(lambda:Z)
   for z in a['layers']:
    if not z['qty']:continue
    m=a['capital_meta'][str(z['id'])];v=D(z['qty'])*D(a['market_marks'][z['sid']]);caps[m['sector']]+=v;stockcaps[z['sid']]+=v;rp[m['role']+'|'+m['pool']]+=v
   tr=[z for z in a['trades'] if z['at'][:10]==path.name[:10]]
   daily.append(dict(day=path.name[:10],NAV=nav,exposure=D(b['inventory'])/nav,available=b['available'],risk=b['resources']['risk'],industries=[dict(sector=s,value=v,weight=v/nav) for s,v in sorted(caps.items(),key=lambda kv:-kv[1])],stocks=[dict(sid=s,value=v,weight=v/nav) for s,v in sorted(stockcaps.items(),key=lambda kv:-kv[1])],role_pool=rp,ACT=a['policy']['act'],budget=x['budget'],Q=x['active']['Q'] if x.get('active') else {},D=x['active']['D'] if x.get('active') else {},buy_gross=sum((D(z['gross_cny']) for z in tr if z['side']=='buy'),Z),sell_gross=sum((D(z['gross_cny']) for z in tr if z['side']=='sell'),Z),active_exits=len(a['exits']),pending=len(x['pending'])))
   # Fixed mother: stock Q=True + fresh canonical CP1; market permission is
   # observed separately from ACT, minlot/resources/actual fills.
   opportunity+=opportunities(x,path.name[:10],names);scope_history.append((path.name[:10],a['policy']['scopes']))
  a=final['account'];bal=a['balance'];oldbal=initial['account']['balance'];newtr=[z for z in a['trades'] if z['at'][:10]>'2025-07-31'];newll=[z for z in ll if z['opened'][:10]>'2025-07-31'];by=defaultdict(list)
  for z in newtr:by[(z['at'],z['security_id'])].append(z)
  trips=[dict(at=k[0],sid=k[1],gross=sum((D(z['gross_cny']) for z in v),Z),fees=sum((D(z['fees_cny']) for z in v),Z),trades=v) for k,v in by.items() if {'buy','sell'}<={z['side'] for z in v}]
  reasons=defaultdict(lambda:dict(parts=0,gross=Z,fees=Z,net_cash=Z))
  for tr in newtr:
   if tr['side']!='sell':continue
   for part in tr['parts']:
    z=reasons[part['reason']];z['parts']+=1;z['gross']+=D(part['net_cash'])+D(part['fee_cny']);z['net_cash']+=D(part['net_cash']);z['fees']+=D(part['fee_cny'])
  capital=defaultdict(lambda:dict(start_inventory=Z,end_inventory=Z,actual_buy_gross=Z,actual_sell_gross=Z))
  for state,field in [(initial,'start_inventory'),(final,'end_inventory')]:
   for z in state['account']['layers']:
    if z['qty']:capital[names[z['sid']]['sector']][field]+=D(z['qty'])*D(state['account']['market_marks'][z['sid']])
  for tr in newtr:capital[names[tr['security_id']]['sector']]['actual_buy_gross' if tr['side']=='buy' else 'actual_sell_gross']+=D(tr['gross_cny'])
  for v in capital.values():
   v['net_actual_gross_funding']=v['actual_buy_gross']-v['actual_sell_gross'];v['mark_and_execution_price_residual']=v['end_inventory']-v['start_inventory']-v['net_actual_gross_funding']
  firstops={}
  for z in opportunity:
   if z['market_permission']:firstops.setdefault((z['sid'],z['offered_context']),z)
  delays=[]
  for (sid,ctx),z in firstops.items():
   candidates=[r for r in ll if r['sid']==sid and r['signal_at'][:10]>=z['day'] and r['source_context']==ctx]
   first=min(candidates,key=lambda r:r['opened']) if candidates else None
   ended=next((d for d,scopes in scope_history if d>z['day'] and (scopes.get(z['permission_scope'],{}).get('context')!=ctx or scopes.get(z['permission_scope'],{}).get('support') is False)),None)
   status='actually_funded_same_context' if first else 'unfunded_market_context_ended' if ended else 'unfunded_market_context_not_ended_at_cutoff_other_stock_constraints_not_inferred'
   calendar=sorted({d for d,_ in scope_history});lag=(calendar.index(first['opened'][:10])-calendar.index(z['day'])) if first and first['opened'][:10] in calendar else None
   delays.append(dict(first_market_qualified=z,first_actual_fill=first['opened'] if first else None,filled_role=first['role'] if first else None,filled_pool=first['pool'] if first else None,source_context=first['source_context'] if first else None,market_session_lag=lag,market_context_ended_close=ended,status=status,observation_cutoff=cut,mother='window-first stock/market-context freshCP1+stockQ and market permit, July1 through actual cutoff; permission is not all-resource executable',no_claim_unfunded_all_censored=True))
  inc={k:pnl[k]-oldpnl[k] for k in pnl};nav=D(bal['nav']);start=D(oldbal['nav']);E.require(abs(sum((z['August_contribution'] for z in stocks),Z)-(nav-start))<D('1e-9'),'August stock wealth bridge')
  record=dict(cell=cell,cursor=pr['cursor'],initial_Jul31_NAV=start,terminal_NAV=nav,August_return=nav/start-1,continuous_Jul1_return=nav/D(1000000)-1,August_max_close_DD=dd,continuous_max_close_DD=globaldd,August_mean_exposure=sum((z['exposure'] for z in daily),Z)/len(daily),August_peak_exposure=max(z['exposure'] for z in daily),end_exposure=daily[-1]['exposure'],August_fee=D(bal['fees_cny'])-D(oldbal['fees_cny']),cumulative_fee=bal['fees_cny'],August_buy_gross=sum((D(z['gross_cny']) for z in newtr if z['side']=='buy'),Z),August_sell_gross=sum((D(z['gross_cny']) for z in newtr if z['side']=='sell'),Z),August_buy_fills=sum(z['side']=='buy' for z in newtr),August_sell_fills=sum(z['side']=='sell' for z in newtr),pnl=pnl,August_accounting_change=inc,August_new_layer_groups=grouped(newll,['role','pool','entry_class']),cumulative_layer_groups=grouped(ll,['role','pool','entry_class']),same_open_roundtrips=trips,same_buy_day_exit_request_layers=[z['layer'] for z in newll if z['same_buy_day_exit_requested']],whole_stocks=len(st),August_funded_stocks=len({z['sid'] for z in newll}),ACT=a['policy']['act'],actual_run=A.read(root/'COMPLETED.json') if (root/'COMPLETED.json').exists() else None,checkpoint=pr,top_positive=stocks[:10],top_negative=list(reversed(stocks[-10:])),first_opportunity_groups=len(delays),first_opportunity_funded=sum(bool(z['first_actual_fill']) for z in delays))
  results.append(record);save(out/(cell+'-STOCKS.json'),stocks);save(out/(cell+'-SECTORS.json'),sectors);save(out/(cell+'-LAYERS.json'),ll);save(out/(cell+'-SALES.json'),ss);save(out/(cell+'-DAILY.json'),daily);save(out/(cell+'-PERFORMANCE.json'),flows);save(out/(cell+'-OPPORTUNITIES.json'),opportunity);save(out/(cell+'-FIRST_OPPORTUNITIES.json'),delays);save(out/(cell+'-RESULT.json'),record)
  save(out/(cell+'-EXIT_REASONS.json'),dict(reasons));save(out/(cell+'-OPPORTUNITY_STATUS_COUNTS.json'),dict(Counter(z['status'] for z in delays)))
  save(out/(cell+'-ACTIVE_CAPITAL_VS_REVALUATION.json'),dict(definition='No held split in August. Inventory delta = actual gross buys - actual gross sells + mark/execution-price residual. Residual is not claimed to be pure passive return.',industries=capital))
  top=stocks[0];positive=sum((max(Z,z['August_contribution']) for z in stocks),Z)
  save(out/(cell+'-LARGEST_CONTRIBUTOR_SENSITIVITY.json'),dict(largest=top,share_of_gross_positive=top['August_contribution']/positive if positive else None,arithmetic_month_wealth_change_without_largest=(nav-start)-top['August_contribution'],not_a_replayed_policy=True,no_claim_capital_or_subsequent_orders_unchanged_under_trade_deletion=True))
  fixed={s for s,v in names.items() if v['name'] in ['上纬新材','德福科技','淳中科技','东阳光','思泉新材']}
  chosen=fixed|{z['sid'] for z in stocks[:3]+stocks[-3:]};chains=[]
  for sid in sorted(chosen):
   layers=[z for z in ll if z['sid']==sid]
   chains.append(dict(sid=sid,name=names[sid]['name'],fixed_old_PVR_control=sid in fixed,stock_summary=next((z for z in stocks if z['sid']==sid),None),actual_trades=[z for z in a['trades'] if z['security_id']==sid],layers=layers,original_supports={oid:s for oid,s in a['supports'].items() if s['original_intent']['sid']==sid},opportunities=[z for z in opportunity if z['sid']==sid],no_hindsight_whitelist=True))
  save(out/(cell+'-ACTUAL_CHAINS.json'),chains)
  save(out/(cell+'-VERIFICATION.json'),dict(passed=True,cell=cell,checks=[z for z in checks if z['cell']==cell],financial_events=0,partial=args.partial))
  print('READ_ONLY_ANALYZED',cell,cut,nav,record['August_return'],flush=True)
 save(out/'RESULTS.json',results);save(out/'VERIFICATION.json',dict(passed=True,cells=args.cells,all_four_complete=(not args.partial and set(args.cells)=={'C10','C20','C10_R0','C20_R0'}),checks=checks,event_states=len(checks),account_events=0,seconds=time.perf_counter()-t,partial=args.partial))
if __name__=='__main__':main()
