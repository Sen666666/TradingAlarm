"""Two named-stock and top-three industry hindsight checks, saved 2023 books only."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,time,hashlib,traceback
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Y=W/'recovery-2023-readiness-20261101';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
M=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json');SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};IM=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');frames={};sources={}
def price(sid,d):
 if sid not in frames:
  p=SM[sid]['refs']['facts'];frames[sid]=pd.read_parquet(p,columns=['raw_close']);sources[p]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
 f=frames[sid];i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0;return n(f.iloc[i].raw_close)
def main():
 started=time.monotonic();rank=[];sector_states={}
 for r in IM:
  q=pd.read_parquet(r['refs']['CP1_input'],columns=['close']);old=q.loc[:'2022-12-30'];yr=q.loc['2023-01-01':'2023-12-31'];assert str(old.index[-1].date())=='2022-12-30' and len(yr)==242 and str(yr.index[-1].date())=='2023-12-29'
  rank.append(dict(sector=r['series'],year_return_pct=100*(float(yr.close.iloc[-1])/float(old.close.iloc[-1])-1),start_price=float(old.close.iloc[-1]),end_price=float(yr.close.iloc[-1]),peak_day=str(yr.close.idxmax().date()),peak_close=float(yr.close.max()),trough_day=str(yr.close.idxmin().date())))
  sector_states[r['series']]=pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index')
 rank.sort(key=lambda x:(-x['year_return_pct'],x['sector']));top={x['sector'] for x in rank[:3]};names={m['sector_id']:m['industry'] for m in M.values()}
 for i,r in enumerate(rank,1):r.update(rank=i,name=names.get(r['sector'],'unknown'),selection='all90 full-calendar return; hindsight evaluation only, no input to strategy')
 save('2023/ALL90_PRICE_RANK.json',rank);output=[]
 for ref in ['Bdiag','C1']:
  root=Y/'runs'/ref/'pair';b=book(root/'B.json.gz');ds=[x for x in rows(root/'daily.jsonl.gz') if day(x['at']).startswith('2023')];assert len(ds)==242
  tx=[x for x in b['trades'] if day(x['at']).startswith('2023')];ls=read(Y/'analysis'/ref/'LAYERS_2023.json');byday={day(x['at']):x for x in ds};weights={};sectors={};peaks={s:(Z,None) for s in ['300308.SZ','300502.SZ']};sector_peaks={s:(Z,None) for s in top}
  for x in ds:
   d=day(x['at']);nav=n(x['nav']);sv=collections.defaultdict(lambda:Z);total=Z
   for sid,q in x['positions'].items():
    value=D(q)*price(sid,d);total+=value;sv[M[sid]['sector_id']]+=value
    if sid in peaks and value/nav>peaks[sid][0]:peaks[sid]=(value/nav,d)
   assert abs(total-n(x['inventory']))<D('.00000001'),(ref,d,'all holding raw mark not equal native daily inventory')
   for s in top:
    if sv[s]/nav>sector_peaks[s][0]:sector_peaks[s]=(sv[s]/nav,d)
  target=['300308.SZ','300502.SZ'];ops=collections.defaultdict(list);fund=collections.defaultdict(list);route=collections.defaultdict(list)
  for x in rows(root/'opportunities.jsonl.gz'):
   if x['day'].startswith('2023') and x['sid'] in target:ops[x['sid']].append(x)
  for x in rows(root/'funding.jsonl.gz'):
   if day(x['at']).startswith('2023') and x['sid'] in target:fund[x['sid']].append(x)
  for x in rows(root/'capacity-checks.jsonl.gz'):
   if day(x['at']).startswith('2023') and x['sid'] in target:route[x['sid']].append(x)
  stocks=[]
  for sid in target:
   f=pd.read_parquet(SM[sid]['refs']['facts']).loc['2023-01-01':'2023-12-31'];cp=pd.read_parquet(SM[sid]['refs']['CP1'],columns=['receipt']).loc['2023-01-01':'2023-12-31'];ii=f[f.i_buy.eq(True)&f.i_target.eq(True)];cc=cp[cp.receipt.eq(True)];qops=[x for x in ops[sid] if x['CP1_id'] and x['mobile_Q'] is True];stage=[x for x in qops if sector_states[x['sector']][x['day']]['E0_valid'] and sector_states[x['sector']][x['day']]['stage']>=2];st=[x for x in tx if x['security_id']==sid];buy=[x for x in st if x['side']=='buy'];sell=[x for x in st if x['side']=='sell'];layer=[x for x in ls if x['sid']==sid]
   peak,peakday=peaks[sid];r=dict(policy=ref,sid=sid,name=M[sid]['name'],raw_I_events=len(ii),first_raw_I=str(ii.index[0].date()) if len(ii) else None,native_CP1=len(cc),first_CP1=str(cc.index[0].date()) if len(cc) else None,Q_pass_CP1=len(qops),first_Q_pass_CP1=qops[0] if qops else None,market_confirmed_Q_CP1=len(stage),first_market_confirmed_Q_CP1=stage[0] if stage else None,first_actual_buy=buy[0] if buy else None,buy_fills=len(buy),cumulative_new_buy_cash=sum((n(x['gross_cny'])+n(x['fees_cny']) for x in buy),Z),sell_fills=len(sell),first_actual_sell=sell[0] if sell else None,last_actual_sell=sell[-1] if sell else None,peak_daily_actual_weight_pct=100*peak,peak_day=peakday,peak_day_active_new_buy_cash=sum((n(x['gross_cny'])+n(x['fees_cny']) for x in buy if day(x['at'])==peakday),Z),closed_positive=sum((n(x['net']) for x in layer if not x['qty'] and n(x['net'])>0),Z),closed_negative=sum((n(x['net']) for x in layer if not x['qty'] and n(x['net'])<0),Z),open_net=sum((n(x['net']) for x in layer if x['qty']),Z),ending_shares=sum(x['qty'] for x in layer),ending_exit_obligation=b['exits'].get(sid),actual_route_rows=route[sid],funding_records=fund[sid],transactions=st,layers=layer,maximum_scope='actual close holdings / own daily NAV, intraday maximum unknown; passive appreciation is not active allocation')
   if not buy:
    first=stage[0] if stage else qops[0] if qops else None;r['first_proven_block']=dict(opportunity=first,barriers=first['barriers'] if first else None,first_recorded_mobile_funding=next((x for x in fund[sid] if x['role']=='mobile'),None),first_actual_mobile_route=next((x for x in route[sid] if x['role']=='mobile'),None),unit_reason='raw reason only unless route explicitly proves minimum rejection; no guessed round-lot diagnosis')
   stocks.append(r)
  inds=[]
  for sector in top:
   st=[x for x in tx if M[x['security_id']]['sector_id']==sector];buy=[x for x in st if x['side']=='buy'];ll=[x for x in ls if x['sector']==sector];peak,d=sector_peaks[sector]
   inds.append(dict(policy=ref,sector=sector,name=names[sector],price_rank=next(x for x in rank if x['sector']==sector),first_actual_new_buy=buy[0] if buy else None,first5_buy_fills=buy[:5],cumulative_new_buy_cash=sum((n(x['gross_cny'])+n(x['fees_cny']) for x in buy),Z),actual_buy_stocks=len({x['security_id'] for x in buy}),buy_fills=len(buy),peak_daily_actual_weight_pct=100*peak,peak_day=d,peak_day_active_new_buy_cash=sum((n(x['gross_cny'])+n(x['fees_cny']) for x in buy if day(x['at'])==d),Z),closed_positive=sum((n(x['net']) for x in ll if not x['qty'] and n(x['net'])>0),Z),closed_negative=sum((n(x['net']) for x in ll if not x['qty'] and n(x['net'])<0),Z),open_net=sum((n(x['net']) for x in ll if x['qty']),Z)))
  save('2023/'+ref+'_NAMED_STOCKS.json',stocks);save('2023/'+ref+'_TOP3_INDUSTRIES.json',sorted(inds,key=lambda x:x['price_rank']['rank']));output.append(dict(policy=ref,stocks=stocks,industries=inds,all242_native_inventory_marks_exact=True))
  print('2023_BEHAVIOR',ref,json.dumps(dict(stocks=[{k:x[k] for k in ['sid','first_raw_I','first_CP1','cumulative_new_buy_cash','buy_fills','peak_daily_actual_weight_pct','peak_day','closed_positive','closed_negative','open_net']} for x in stocks],industries=[{k:x[k] for k in ['sector','name','cumulative_new_buy_cash','peak_daily_actual_weight_pct','peak_day']} for x in inds]),ensure_ascii=False,default=str),flush=True)
 save('2023/COMPLETION.json',dict(passed=True,policies=2,full90_rank_preserved=True,stock_specific_treatment=False,account_replays=0,new_indicators=0,seconds=time.monotonic()-started));save('2023/SOURCE_SHA256.json',sources);print('BEHAVIOR_DONE',round(time.monotonic()-started,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('2023/ERROR.json',dict(reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
