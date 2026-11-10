from pathlib import Path
import os,csv,json,math,hashlib,collections,datetime
OUT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(OUT/'mpl-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
ROOT=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
BASE=ROOT/'TradingAlarm/research/data/ths-index-history-9603-20261018'
PILOT=ROOT/'research_rounds/sector-stock-20261021/coverage/pilot-batch-01.json'
SYMS={'URFI881155':('THS Banks','银行'),'URFI881121':('THS Semiconductors','半导体'),'UHKIHSCFIN':('Hang Seng Financials','恒生金融业'),'UHKIHSCTEC':('Hang Seng Information Technology','恒生资讯科技业')}
START='2013-01-01'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary={'created_date':'2026-10-22','scope':'offline source-quality audit and descriptive raw charts only; no signal/state/account computed','pilot_path':str(PILOT),'pilot_sha256':sha(PILOT),'selection_changed':False,'target_start':START,'price_unit':'provider index points; base/launch and historical methodology unverified','volume_unit':'provider field 13; physical unit and historical constituent aggregation not independently established; no normalization/fill or amount substitute','amount_unit':'provider field 19; monetary currency/unit not independently established; displayed only as raw provider value','classification':'THS 881 family described as second-level in old protocol, but source metadata itself marks publication facts unverified; HK names from quote response, historical taxonomy/member mapping not established','sources':{},'symbols':{}}
for rel in ['protocol.json','server-names.json','integrity.json']:
 p=BASE/rel;summary['sources'][str(p)]=sha(p)
for rel in ['TradingAlarm/market.py','TradingAlarm/research/results/ths-industry-snapshot/review.json','docs/reviews/2026-10-19-tradingalarm/data-audit.json']:
 p=ROOT/rel;summary['sources'][str(p)]=sha(p)
anomalies=[]
all_rows={}
for sym,(name,cn) in SYMS.items():
 p=BASE/'canonical'/f'{sym}.csv';ckp=BASE/'checkpoints'/f'{sym}.json';ck=json.loads(ckp.read_text())
 raw=list(csv.DictReader(p.open()));rows=[]
 for r in raw:
  q={'date':r['date']}
  for k in ['open','high','low','close','volume','amount']:
   try:q[k]=float(r[k])
   except (ValueError,TypeError):q[k]=None
  q['volume_kind']='missing' if q['volume'] is None else ('constant_one_unknown' if q['volume']==1 else ('nonpositive_unknown' if q['volume']<=0 else 'positive_variable'))
  q['bad_price']=any(q[k] is None or not math.isfinite(q[k]) or q[k]<=0 for k in ['open','high','low','close'])
  q['bad_geometry']=False if q['bad_price'] else (q['high']<max(q['open'],q['close']) or q['low']>min(q['open'],q['close']) or q['high']<q['low'])
  rows.append(q)
  reasons=[]
  if q['bad_price']:reasons.append('invalid_price')
  if q['bad_geometry']:reasons.append('OHLC_geometry')
  if q['volume_kind']!='positive_variable':reasons.append(q['volume_kind'])
  if q['amount'] is None or q['amount']<=0:reasons.append('amount_unknown')
  if reasons:anomalies.append(dict(symbol=sym,date=q['date'],target_2013_onward=q['date']>=START,reasons=';'.join(reasons),**{k:r[k] for k in ['open','high','low','close','volume','amount']}))
 all_rows[sym]=rows
 def stats(rr):
  return dict(rows=len(rr),first=rr[0]['date'],last=rr[-1]['date'],invalid_price=sum(r['bad_price'] for r in rr),bad_ohlc_geometry=sum(r['bad_geometry'] for r in rr),missing_volume=sum(r['volume_kind']=='missing' for r in rr),constant_one_volume_unknown=sum(r['volume_kind']=='constant_one_unknown' for r in rr),nonpositive_volume=sum(r['volume_kind']=='nonpositive_unknown' for r in rr),positive_variable_volume=sum(r['volume_kind']=='positive_variable' for r in rr),amount_missing_or_nonpositive=sum(r['amount'] is None or r['amount']<=0 for r in rr),flat_ohlc=sum(len({r[k] for k in ['open','high','low','close']})==1 for r in rr),duplicate_dates=len(rr)-len({r['date'] for r in rr}))
 target=[r for r in rows if r['date']>=START]
 groups=[]
 for r in rows:
  if not groups or groups[-1]['kind']!=r['volume_kind']:groups.append(dict(kind=r['volume_kind'],first=r['date'],last=r['date'],rows=1))
  else:groups[-1]['last']=r['date'];groups[-1]['rows']+=1
 gaps=[]
 for a,b in zip(rows,rows[1:]):
  days=(datetime.date.fromisoformat(b['date'])-datetime.date.fromisoformat(a['date'])).days
  if days>14:gaps.append(dict(previous=a['date'],next=b['date'],calendar_days=days))
 detail=dict(name=cn,source_path=str(p),source_sha256=sha(p),schema=list(raw[0]),checkpoint_sha256=sha(ckp),checkpoint_hash_matches=sha(p)==ck['canonical_sha256'],checkpoint_status=ck['status'],overlap_conflicts=ck.get('overlap_conflicts'),rows_dropped_by_parser=ck.get('rows_dropped_by_parser'),full=stats(rows),target=stats(target),volume_regimes=groups,gaps_over_14_calendar_days=gaps,bad_ohlc_dates=[r['date'] for r in rows if r['bad_price'] or r['bad_geometry']],first_raw_row=raw[0],last_raw_row=raw[-1])
 summary['symbols'][sym]=detail
 # Keep a row-complete copy of the selected inputs; flags are separate and do not replace source values.
 with (OUT/f'{sym}-annotated.csv').open('x',newline='') as f:
  fields=list(raw[0])+['volume_kind','bad_price','bad_geometry'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for orig,r in zip(raw,rows):w.writerow(dict(orig,volume_kind=r['volume_kind'],bad_price=r['bad_price'],bad_geometry=r['bad_geometry']))
 x=[datetime.date.fromisoformat(r['date']) for r in target]
 y=lambda k:np.array([np.nan if r[k] is None else r[k] for r in target],dtype=float)
 fig,axes=plt.subplots(3,1,figsize=(16,9),sharex=True,gridspec_kw={'height_ratios':[3,1.35,1.1]})
 ax,vax,aax=axes
 ax.fill_between(x,y('low'),y('high'),color='#8096a8',alpha=.35,label='Daily low-high (raw)')
 ax.plot(x,y('close'),color='#164b73',lw=.8,label='Raw close');ax.plot(x,y('open'),color='#73a2ba',lw=.35,alpha=.5,label='Raw open')
 bad=[i for i,r in enumerate(target) if r['bad_price'] or r['bad_geometry']]
 if bad:ax.scatter([x[i] for i in bad],y('close')[bad],color='red',marker='x',s=35,label='Invalid OHLC - retained, not repaired')
 ax.set_ylabel('Provider index points');ax.legend(loc='upper left',ncol=3,fontsize=8)
 vol=y('volume');ok=np.array([r['volume_kind']=='positive_variable' for r in target]);unknown=~ok
 vax.bar(np.array(x)[ok],vol[ok],width=1.1,color='#367e87',label='Positive varying field 13 (unit unverified)')
 # Unknown flags are drawn in axis coordinates, never imputed into the numeric series.
 if unknown.any():
  vax.scatter(np.array(x)[unknown],np.full(unknown.sum(),.04),transform=vax.get_xaxis_transform(),s=3,color='#d97706',label='Missing / field 13 = 1: UNKNOWN, not low volume',zorder=4)
  for g in groups:
   if g['kind']!='positive_variable' and g['last']>=START:
    vax.axvspan(datetime.date.fromisoformat(max(g['first'],START)),datetime.date.fromisoformat(g['last']),color='#f3d5a3',alpha=.3)
 vax.set_ylabel('Raw volume field 13');vax.legend(loc='upper left',fontsize=8)
 aax.plot(x,y('amount'),color='#725d91',lw=.5,label='Raw amount field 19 (unit unverified; not volume substitute)');aax.set_ylabel('Raw amount field 19');aax.legend(loc='upper left',fontsize=8)
 for a in axes:a.grid(alpha=.2)
 aax.xaxis.set_major_locator(mdates.YearLocator(2));aax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
 ax.set_title(f'{name} | {sym} | raw descriptive input review\n{target[0]["date"]} to {target[-1]["date"]}; no state, trend estimate or account overlay',loc='left',fontsize=14)
 fig.text(.055,.025,f'Target rows {len(target)} | OHLC anomalies {len(bad)} | unknown volume {int(unknown.sum())} | sha256 {sha(p)[:20]}…\nFull-history QA retained in review-summary.json. Classification/member history and field units remain unverified.',fontsize=9)
 fig.tight_layout(rect=[0,.065,1,1]);fig.savefig(OUT/f'{sym}-raw-2013-2026.png',dpi=150);plt.close(fig)
# Exact peer-calendar discrepancy is a source comparison, not an official exchange calendar conclusion.
bank={r['date'] for r in all_rows['URFI881155']};semi={r['date'] for r in all_rows['URFI881121']}
summary['calendar_comparison']={'reference':'peer dates only, not official calendar','bank_absent_vs_semiconductor':sorted(semi-bank),'semiconductor_absent_vs_bank':sorted(bank-semi),'target_bank_absent_vs_semiconductor':[d for d in sorted(semi-bank) if d>=START]}
with (OUT/'anomalies.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(anomalies[0]));w.writeheader();w.writerows(anomalies)
(OUT/'review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({s:d['target'] for s,d in summary['symbols'].items()},ensure_ascii=False,indent=2))
