"""Original IX lifted to all 90 sector indices; analytical proxy, not tradable."""
from common import *
from fast_single import run as single

def portfolio(o,c,target,event,floor,rank,initial,*,only_new,slots=3,allocation=.3,gross=.9):
 cash=1.;pos={};pending={};fills=[];ledger=[];fee=.0005;slip=.0005
 def candidates(t):
  ids=np.flatnonzero(initial if t<0 else (target[t]&event[t]));return sorted(ids,key=lambda j:(-rank[max(0,t),j] if math.isfinite(rank[max(0,t),j]) else math.inf,j))
 for j in candidates(-1)[:slots]:pending[j]=('buy',allocation,float(floor[0,j]),-1)
 for t in range(len(o)):
  for j,(side,budget,fl,sig) in list(pending.items()):
   if not math.isfinite(o[t,j]):continue
   del pending[j];price=o[t,j]
   if side=='sell':
    if j in pos:qty=pos.pop(j);paid=qty*(price-price*slip)*fee;value=qty*(price-price*slip);cash+=value-paid;fills.append(dict(t=t,j=int(j),side='sell',quantity=qty,price=price-price*slip,fee=paid,signal=sig))
   elif j not in pos and (t==0 or target[t-1,j]) and price>fl:
    amount=min(cash,budget);px=price+price*slip;qty=amount/(px*(1+fee));paid=qty*px*fee;cash-=qty*px+paid;pos[j]=qty;fills.append(dict(t=t,j=int(j),side='buy',quantity=qty,price=px,fee=paid,signal=sig))
  values={j:q*c[t,j] for j,q in pos.items()};nav=cash+sum(values.values());reserved=sum(x[1] for x in pending.values() if x[0]=='buy')
  for j in list(pos):
   if not target[t,j] and j not in pending:pending[j]=('sell',0.,floor[t,j],t)
  occupied=set(pos)|set(pending);eligible=candidates(t)
  for j in eligible:
   if j in occupied or len(occupied)>=slots:continue
   if only_new and not (target[t,j] and (t==0 or not target[t-1,j])):continue
   available=max(0.,cash-reserved);room=max(0.,gross*nav-sum(values.values())-reserved);budget=min(allocation*nav,available,room)
   if budget<=0:continue
   pending[j]=('buy',budget,floor[t,j],t);reserved+=budget;occupied.add(j)
  if t==len(o)-1:
   pending={}
   for j,qty in list(pos.items()):
    px=c[t,j]-c[t,j]*slip;paid=qty*px*fee;cash+=qty*px-paid;fills.append(dict(t=t,j=int(j),side='sell',quantity=qty,price=px,fee=paid,signal='terminal'));del pos[j]
   nav=cash
  assert cash>=-1e-12 and len(pos)<=slots
  ledger.append(dict(t=t,nav=nav,cash=cash,inventory=nav-cash,positions=list(pos)))
 # Independent double-entry replay of every proxy fill, including costs.
 cc=1.;qq={};cursor=0
 for t,l in enumerate(ledger):
  while cursor<len(fills) and fills[cursor]['t']==t:
   f=fills[cursor];cursor+=1;j=f['j'];q=f['quantity'];v=q*f['price']
   if f['side']=='buy':cc-=v+f['fee'];qq[j]=qq.get(j,0)+q
   else:cc+=v-f['fee'];qq[j]=qq.get(j,0)-q
  check=cc+sum(q*c[t,j] for j,q in qq.items());assert abs(check-l['nav'])<1e-9
 nav=np.array([x['nav'] for x in ledger]);return dict(net_return=nav[-1]-1,max_drawdown=float(-(nav/np.maximum.accumulate(np.r_[1,nav])[1:]-1).min()),buy_fills=sum(f['side']=='buy' for f in fills),mean_exposure=float(np.mean([(l['inventory']/l['nav']) for l in ledger]))),ledger,fills

def main():
 out=HERE/'sector-proxy';out.mkdir(exist_ok=False);z=np.load(OLD/'h1/matrix.npz');all_dates=pd.DatetimeIndex(z['dates']);mask=(all_dates>=START)&(all_dates<=END);dates=all_dates[mask];symbols=[str(s) for s in z['symbols']];sectors=sorted(s for s in symbols if s.startswith('URFI'));idx={s:i for i,s in enumerate(symbols)};rank=z['score'][mask][:,[idx[s] for s in sectors]];meta=read(OLD/'inputs-v2/metadata.json');names={v['sector_id']:v['industry'] for v in meta.values() if v.get('sector_id')};recs={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']};shape=(len(dates),len(sectors));o=np.full(shape,np.nan);c=o.copy();target=np.zeros(shape,bool);event=target.copy();floor=o.copy();initial=[];solo=[]
 for j,sid in enumerate(sectors):
  sf=pd.read_parquet(HERE/'sector-states'/f'{sid}.parquet');raw=pd.read_parquet(OLD/'prepared-v2'/recs[sid]['files']['signal']['path']);raw=raw.loc[sf.index];d=raw.loc[START:END];a=sf.loc[d.index];n=sf.index.searchsorted(START);prev=sf.iloc[n-1] if n else None;active=bool(prev is not None and prev.ready and prev.ix_target and prev.grade>=2);ini=dict(active=active,floor=float(prev.ix_floor) if active else None);state=pd.DataFrame(dict(target=a.ix_target,floor=a.ix_floor,buy_event=a.buy_event),index=a.index);st,_,_=single(d,state,ini);solo.append(dict(symbol=sid,name=names.get(sid,sid),**st));q=raw.reindex(dates);p=sf.reindex(dates,method='ffill');o[:,j]=q.open;c[:,j]=q.close.ffill();target[:,j]=p.ix_target.fillna(0).astype(bool);event[:,j]=p.buy_event.fillna(False).astype(bool)&q.open.notna();floor[:,j]=p.ix_floor;initial.append(active)
  if active:floor[0,j]=ini['floor']
 # Source price holes remain explicitly counted, never manufactured opens.
 write(out/'pre-account-protocol.json',dict(recorded_at=now(),type='nontradable_sector_index_proxy_only',indices=90,strategies=['ACTIVE_current_IX_event','NEW_sector_IX_episode'],max_indices=3,initial_fraction_each=.3,new_gross=.9,fees_each=.0005,slippage_each=.0005,no_new_signal_formula=True,raw_open_missing=int(np.isnan(o).sum()),sha256={str((HERE/'code/sector_proxy.py').relative_to(ROOT)):sha(__file__)}))
 results=[];allcurves=[];allfills=[]
 for label,new in [('ACTIVE',False),('NEW',True)]:
  st,ledger,fills=portfolio(o,c,target,event,floor,rank,np.array(initial),only_new=new);results.append(dict(policy=label,**st))
  for l in ledger:allcurves.append(dict(policy=label,date=str(dates[l['t']].date()),nav=l['nav'],cash=l['cash'],positions='|'.join(sectors[j] for j in l['positions'])))
  for f in fills:allfills.append(dict(policy=label,date=str(dates[f['t']].date()),sector=sectors[f['j']],name=names.get(sectors[f['j']]),**f))
 pd.DataFrame(solo).to_csv(out/'all-90-standalone.csv',index=False);pd.DataFrame(results).to_csv(out/'summary.csv',index=False);pd.DataFrame(allcurves).to_csv(out/'curves.csv',index=False);pd.DataFrame(allfills).to_csv(out/'fills.csv',index=False);write(out/'receipt.json',dict(passed=True,proxy_cash_quantity_replayed=True,not_stock_account=True,sector_index_not_directly_tradeable=True,underlying_data_and_IX_unchanged=True));print(pd.DataFrame(results).to_string(index=False),flush=True);print(dict(solo_mean=float(pd.DataFrame(solo).net_return.mean()),solo_median=float(pd.DataFrame(solo).net_return.median()),positive_fraction=float(pd.DataFrame(solo).net_return.gt(0).mean())),flush=True)
if __name__=='__main__':main()
