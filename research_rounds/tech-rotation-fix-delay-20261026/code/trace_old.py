from study_common import *
import collections
AIDS=['I__S0_base','I__S0_delay1'];objs={a:read(BASE/'accounts-v2'/f'{a}.json') for a in AIDS};meta=read(OLD/'inputs-v2/metadata.json')
DAYS=collections.defaultdict(dict);DECS=collections.defaultdict(dict)
for row in rows(BASE/'accounts-v2/daily.jsonl.gz'):
 if row['account'] in AIDS:DAYS[row['account']][row['at'][:10]]=row
for row in rows(BASE/'accounts-v2/decisions.jsonl.gz'):
 if row['account'] in AIDS:DECS[row['account']][row['at'][:10]]=row
facts={};cases=[];orders=[]
for aid,obj in objs.items():
 reserves={r['order_id']:r for r in obj['audit_log'] if r['kind']=='reserve'};filled=collections.defaultdict(list)
 for r in obj['audit_log']:
  if r['kind']=='fill' and r['receipt']['side']=='buy':filled[r['order_id']].append(r['receipt'])
 for oid,r in reserves.items():
  ff=filled[oid];orders.append(dict(account=aid,symbol=r['sid'],signal_day=r['decision_at'][:10],order_id=oid,filled=bool(ff),first_fill=ff[0]['at'] if ff else None,fill_gross=sum(float(f['gross_cny']) for f in ff),delay_credit=any(x['kind']=='buy_day_expiry' and x['sid']==r['sid'] and x.get('delay_credit') and x['at'][:10]==r['decision_at'][:10] for x in obj['audit_log'])))
for aid in AIDS:
 for sid in ['688498.SH','688195.SH','603115.SH','301183.SZ','688048.SH']:
  for r in orders:
   if r['account']!=AIDS[0] or r['symbol']!=sid or not r['filled']:continue
   day=r['signal_day'];d=DAYS[aid][day];z=DECS[aid][day];p=collections.Counter(meta[s]['industry'] for s in list(d['positions'])+list(d['pending_buys']));xx={k:z.get(k) for k in ['accepted','rejected','selected']};row=dict(aid=aid,symbol=sid,name=meta[sid]['name'],signal_day=day,base_fill=r['first_fill'],eligible=sid in z['eligible'],held=int(d['positions'].get(sid,0)),pending=sid in d['pending_buys'],positions={meta[s]['name']:n for s,n in d['positions'].items()},pending_names=[meta[s]['name'] for s in d['pending_buys']],industries=dict(p),nav=d['nav'],available=d['available'],decision=xx)
   row['same_signal_order']=[x for x in orders if x['account']==aid and x['symbol']==sid and x['signal_day']==day]
   cases.append(row)
pd.DataFrame(orders).to_csv(HERE/'old-I-orders.csv',index=False);write(HERE/'old-I-cases.json',cases)
for r in cases:
 if r['aid']==AIDS[1]:print(r)
# Exact raw drawdown interval plus all stock daily net contributions.
curves=pd.read_csv(BASE/'analysis/curves.csv');con=pd.read_csv(BASE/'analysis/contributions.csv');print('CONTRIBUTION_COLUMNS',list(con.columns))
for aid in AIDS:
 f=curves[curves.account.eq(aid)].copy();tr=f.loc[f.drawdown.idxmax()];past=f[f.date.le(tr.date)];peak=past.loc[past.nav.idxmax()];print('DRAWDOWN',aid,dict(start=peak.date,trough=tr.date,peak=peak.nav,trough_nav=tr.nav,drop=tr.drawdown))
