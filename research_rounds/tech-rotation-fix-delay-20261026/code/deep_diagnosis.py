from study_common import *
import collections

def main():
 oo=pd.read_csv(HERE/'old-I-orders.csv');base=oo[oo.account.eq('I__S0_base')].copy();delay=oo[oo.account.eq('I__S0_delay1')].copy();summary={}
 for label,x in [('base',base),('delay',delay)]:summary[label]=dict(reservations=len(x),filled_orders=int(x.filled.sum()),zero_fill=int((~x.filled).sum()),origin_events=int(x[['symbol','signal_day']].drop_duplicates().shape[0]))
 join=base.merge(delay,on=['symbol','signal_day'],suffixes=('_base','_delay'));join.to_csv(HERE/'matched-old-order-origins.csv',index=False);summary['matched_origins']=dict(all=len(join),both_filled=int((join.filled_base&join.filled_delay).sum()),base_only_fill=int((join.filled_base&~join.filled_delay).sum()),delay_only_fill=int((~join.filled_base&join.filled_delay).sum()))
 objs={a:read(BASE/'accounts-v2'/f'{a}.json') for a in ['I__S0_base','I__S0_delay1']};meta=read(OLD/'inputs-v2/metadata.json');facts={};detail=[];price_matches=[]
 for _,j in join[join.filled_base&join.filled_delay].iterrows():
  fills=[]
  for key,aid in [('base','I__S0_base'),('delay','I__S0_delay1')]:
   ff=[r['receipt'] for r in objs[aid]['audit_log'] if r['kind']=='fill' and r['order_id']==j['order_id_'+key] and r['receipt']['side']=='buy'];q=sum(x['shares'] for x in ff);p=sum(float(x['gross_cny']) for x in ff)/q;fills.append((q,p))
  price_matches.append(dict(symbol=j.symbol,name=meta[j.symbol]['name'],signal_day=j.signal_day,base_at=j.first_fill_base,delay_at=j.first_fill_delay,base_q=fills[0][0],delay_q=fills[1][0],base_price=fills[0][1],delay_price=fills[1][1],price_change=fills[1][1]/fills[0][1]-1))
 pd.DataFrame(price_matches).to_csv(HERE/'matched-buy-price-changes.csv',index=False);summary['matched_price_changes']=dict(n=len(price_matches),median=float(np.median([x['price_change'] for x in price_matches])),mean=float(np.mean([x['price_change'] for x in price_matches])))
 # Reconcile the biggest drawdown, and ordinary/tail contribution without top hindsight filters.
 cv=pd.read_csv(BASE/'analysis/curves.csv');con=pd.read_csv(BASE/'analysis/contributions.csv');dd=[]
 for aid in objs:
  f=cv[cv.account.eq(aid)];tr=f.loc[f.drawdown.idxmax()];pk=f[f.date.le(tr.date)].loc[lambda z:z.nav.eq(z.nav.max())].iloc[0];part=con[con.account.eq(aid)&con.date.gt(pk.date)&con.date.le(tr.date)];z=part.groupby('symbol').net_contribution.sum().sort_values();assert abs(z.sum()-(tr.nav-pk.nav))<1e-6
  for sid,v in z.items():dd.append(dict(account=aid,start=pk.date,trough=tr.date,symbol=sid,name=meta[sid]['name'],net_contribution=float(v)))
  summary[aid+'_drawdown']=dict(peak_date=pk.date,trough_date=tr.date,peak_nav=float(pk.nav),trough_nav=float(tr.nav),loss=float(pk.nav-tr.nav),drawdown=float(tr.drawdown),top_losses=[dict(symbol=s,name=meta[s]['name'],loss=float(-v)) for s,v in z.head(6).items()])
 pd.DataFrame(dd).to_csv(HERE/'old-I-drawdown-contributions.csv',index=False)
 # Every original base filled intent: was the delayed account already in, pending,
 # capacity constrained, or did it lose the exact reserved event to expiry?
 days={};decs={}
 for r in rows(BASE/'accounts-v2/daily.jsonl.gz'):
  if r['account']=='I__S0_delay1':days[r['at'][:10]]=r
 for r in rows(BASE/'accounts-v2/decisions.jsonl.gz'):
  if r['account']=='I__S0_delay1':decs[r['at'][:10]]=r
 for r in base[base.filled].itertuples():
  d=days[r.signal_day];z=decs[r.signal_day];same=delay[delay.symbol.eq(r.symbol)&delay.signal_day.eq(r.signal_day)];occ=list(d['positions'])+list(d['pending_buys']);sectors=collections.Counter(meta[s]['sector_id'] for s in occ);sec=meta[r.symbol]['sector_id'];capacity=[]
  if len(occ)>=6:capacity.append('six_slots')
  if sectors[sec]>=2:capacity.append('two_per_industry')
  if sec not in sectors and len(sectors)>=3:capacity.append('three_industries')
  if len(same):reason='same_origin_filled' if same.filled.any() else 'same_origin_zero_fill'
  elif r.symbol in d['positions']:reason='already_holding'
  elif r.symbol in d['pending_buys']:reason='other_origin_pending'
  elif r.symbol not in z['eligible']:reason='not_eligible'
  elif capacity:reason='capacity_blocked'
  else:reason='ranking_or_budget_or_minimum'
  detail.append(dict(symbol=r.symbol,name=meta[r.symbol]['name'],signal_day=r.signal_day,base_fill=r.first_fill,classification=reason,capacity=';'.join(capacity),occupancy=len(occ),industries=len(sectors),available=float(d['available']),delayed_nav=float(d['nav'])))
 pd.DataFrame(detail).to_csv(HERE/'base-filled-intent-delay-status.csv',index=False);summary['base_filled_intents_delayed_status']=dict(collections.Counter(x['classification'] for x in detail))
 # Causal originating reservations for holdings that block source on 2025-07-02.
 target=days['2025-07-02'];blocking=[]
 for sid in target['positions']:
  fills=[r for r in objs['I__S0_delay1']['audit_log'] if r['kind']=='fill' and r['receipt']['security_id']==sid and r['receipt']['side']=='buy' and r['receipt']['at'][:10]<='2025-07-02'];r=fills[-1];oid=r['order_id'];o=next(x for x in objs['I__S0_delay1']['audit_log'] if x['kind']=='reserve' and x['order_id']==oid);same=base[base.symbol.eq(sid)&base.signal_day.eq(o['decision_at'][:10])]
  blocking.append(dict(symbol=sid,name=meta[sid]['name'],signal_day=o['decision_at'][:10],fill=r['receipt']['at'],same_base_origin=same.to_dict('records')))
 summary['source_blocking_origin']=blocking
 write(HERE/'old-I-deep-summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
