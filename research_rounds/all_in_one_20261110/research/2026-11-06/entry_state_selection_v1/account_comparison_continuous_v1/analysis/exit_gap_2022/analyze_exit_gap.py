"""2022 PVR sell execution-reference attribution; no account replay or future prices."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import sys,json,pickle,hashlib,csv,ast
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;ROOT=O.parent.parent;OLD=O.parent/'2022_loss_attribution'
sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
P=ROOT/'run_1200000/latest_checkpoint/checkpoint-2022-12-30.pkl'
PREP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared');Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,indent=2,default=str,allow_nan=False))
def main():
 data=P.read_bytes();h=hashlib.sha256(data).hexdigest();assert h==read(P.with_suffix('.json'))['sha256']==read(P.with_suffix('.provenance.json'))['checkpoint_sha256'];x=pickle.loads(data);del data
 a=x['accounts']['PVR'];assert a['initial_cash']==D(1200000)and str(x['last_completed_event'])[:10]=='2022-12-30'
 records={r['series_id']:r for r in read(PREP/'manifest.json')['series']};source={str(P):h,str(PREP/'manifest.json'):sha(PREP/'manifest.json')};raw={};actions={}
 for sid in {t['security_id']for t in a['trades']if t['side']=='sell'}:
  rec=records[sid];p=Path(rec['raw']['path']);assert sha(p)==rec['raw']['sha256'];source[str(p)]=sha(p)
  f=pd.read_parquet(p);f.index=pd.DatetimeIndex(pd.to_datetime(f.trade_date));assert f.index.is_unique and f.index.is_monotonic_increasing
  ok=f.price_eligible.eq(True)&f.observed_bar.eq(True)&~f.synthetic_event_bar.eq(True)&np.isfinite(f.close)&f.close.gt(0)
  raw[sid]=f[ok]
  ar=rec['adjustment']['actions'];p=Path(ar['path']);assert sha(p)==ar['sha256'];source[str(p)]=sha(p);actions[sid]=read(p)['events']
 requests=[r for r in a['audit_log']if r['kind']=='pilot_layer_exit'];layeropened={r['id']:r['opened']for r in a['layers']}
 trades=[];lookup={}
 for t in a['trades']:
  if t['side']!='sell':continue
  sid=t['security_id'];day=pd.Timestamp(t['at'].date());f=raw[sid];ix=f.index.searchsorted(day,side='left')-1
  ref=None;prior=None;used=[]
  if ix>=0:
   prior=f.index[ix];ref=D(str(f.close.iloc[ix]));assert prior<day
   for e in sorted(actions[sid],key=lambda e:e['effective_date']):
    if str(prior.date())<e['effective_date']<=str(day.date()):
     ref=(ref-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])));used.append(e)
   if not ref.is_finite()or ref<=0:ref=None
  q=D(t['shares']);op=t['raw_open'];px=t['price'];fee=t['fees_cny'];assert t['gross_cny']==q*px
  req=[]
  for part in t['parts']:
   rr=[r for r in requests if part['layer']in r['layers']and layeropened[part['layer']]<=r['at']<t['at']]
   req.append(dict(layer=part['layer'],first_request=str(min(r['at']for r in rr))if rr else None,latest_request=str(max(r['at']for r in rr))if rr else None))
  row=dict(receipt_id=t['receipt_id'],sid=sid,at=str(t['at']),reason=t['reason'],shares=t['shares'],prior_actual_close_day=str(prior.date())if prior is not None else None,prior_actual_close=str(f.close.iloc[ix])if ix>=0 else None,prior_close_ex_reference=ref,raw_open=op,actual_price=px,actions_between=used,raw_open_gap=q*(op-ref)if ref is not None else None,slippage_price_effect=q*(px-op),sell_fee=fee,total_price_mark_difference=q*(px-ref)if ref is not None else None,total_net_execution_mark_difference=q*(px-ref)-fee if ref is not None else None,request_clocks=req,reference_known=ref is not None)
  if ref is not None:assert row['raw_open_gap']+row['slippage_price_effect']==row['total_price_mark_difference']
  trades.append(row);lookup[t['receipt_id']]=row
 # Fee-inclusive buy basis, native split rounding, exact sell-part allocation.
 costs={};qtys={};sids={};parts=[]
 ev=[(t['at'],1,i,'trade',t)for i,t in enumerate(a['trades'])]+[(r['at'],0,i,'split',r)for i,r in enumerate(a['journal'])if r['kind']=='actual_split']
 for at,_,i,kind,t in sorted(ev,key=lambda z:z[:3]):
  if kind=='split':
   ks=[k for k in qtys if sids[k]==t['sid']and qtys[k]>0];old=sum(qtys[k]for k in ks);qs=[int(D(qtys[k])*t['ratio'])for k in ks];target=int(D(old)*t['ratio'])
   for j in range(target-sum(qs)):qs[j%len(qs)]+=1
   for k,q in zip(ks,qs):assert q>0;qtys[k]=q
  elif t['side']=='buy':k=t['layer'];sids[k]=t['security_id'];qtys[k]=t['shares'];costs[k]=t['gross_cny']+t['fees_cny']
  else:
   row=lookup[t['receipt_id']];ref=row['prior_close_ex_reference']
   for p in t['parts']:
    k=p['layer'];q=D(p['shares']);basis=costs[k]*q/D(qtys[k]);costs[k]-=basis;qtys[k]-=p['shares'];fee=t['fees_cny']*q/D(t['shares'])
    r=dict(layer=k,sid=t['security_id'],at=str(at),reason=t['reason'],shares=p['shares'],actual_realized_net=p['net_cash']-basis,buy_basis_including_fee=basis,preclose_reference_pnl_before_sell_fee=q*ref-basis if ref is not None else None,raw_open_gap=q*(t['raw_open']-ref)if ref is not None else None,slippage_price_effect=q*(t['price']-t['raw_open']),sell_fee=fee)
    if ref is not None:assert abs(r['preclose_reference_pnl_before_sell_fee']+r['raw_open_gap']+r['slippage_price_effect']-fee-r['actual_realized_net'])<D('1e-8')
    parts.append(r)
 for r in a['layers']:assert qtys[r['id']]==r['qty']
 rounds=[];src=OLD/'STOCK_ROUNDS_2022.csv';source[str(src)]=sha(src);div={r['id']:r['dividend']for r in a['layers']}
 for r in csv.DictReader(src.open()):
  if r['account']!='PVR'or not r['closed']:continue
  ids=set(ast.literal_eval(r['layer_ids']));pp=[p for p in parts if p['layer']in ids];known=all(p['raw_open_gap']is not None for p in pp);income=sum((div[k]for k in ids),Z);actual=sum((p['actual_realized_net']for p in pp),Z)+income;assert abs(actual-D(r['pnl']))<D('1e-8')
  out=dict(sid=r['sid'],round_id=r['id'],opened=r['opened'],closed=r['closed'],actual_round_pnl=actual,all_references_known=known,dividend_accrual=income,preclose_reference_pnl_before_sell_fee=sum((p['preclose_reference_pnl_before_sell_fee']for p in pp),Z)+income if known else None,raw_open_gap=sum((p['raw_open_gap']for p in pp),Z)if known else None,slippage_price_effect=sum((p['slippage_price_effect']for p in pp),Z),sell_fee=sum((p['sell_fee']for p in pp),Z))
  if known:assert abs(out['preclose_reference_pnl_before_sell_fee']+out['raw_open_gap']+out['slippage_price_effect']-out['sell_fee']-actual)<D('1e-8')
  rounds.append(out)
 groups=[]
 for reason in sorted({r['reason']for r in trades}):
  rr=[r for r in trades if r['reason']==reason];known=[r for r in rr if r['reference_known']];groups.append(dict(reason=reason,sell_fills=len(rr),reference_known=len(known),raw_open_gap=sum((r['raw_open_gap']for r in known),Z),slippage_price_effect=sum((r['slippage_price_effect']for r in rr),Z),sell_fee=sum((r['sell_fee']for r in rr),Z),net_execution_mark_difference=sum((r['total_net_execution_mark_difference']for r in known),Z)))
 losing=[r for r in rounds if r['actual_round_pnl']<0];assert len(losing)==562;known=[r for r in losing if r['all_references_known']]
 loss_summary=dict(losing_complete_rounds=len(losing),matched_reference_rounds=len(known),preclose_reference_negative_rounds=sum(r['preclose_reference_pnl_before_sell_fee']<0 for r in known),preclose_reference_nonnegative_but_actual_loss=sum(r['preclose_reference_pnl_before_sell_fee']>=0 for r in known),actual_loss=sum((r['actual_round_pnl']for r in known),Z),preclose_reference_pnl_before_sell_fee=sum((r['preclose_reference_pnl_before_sell_fee']for r in known),Z),raw_open_gap=sum((r['raw_open_gap']for r in known),Z),slippage_price_effect=sum((r['slippage_price_effect']for r in known),Z),sell_fee=sum((r['sell_fee']for r in known),Z))
 examples=[r for r in trades if(r['sid']=='000620.SZ'and '2022-01-12'<=r['at'][:10]<='2022-02-08')or(r['sid']=='002911.SZ'and '2022-07-26'<=r['at'][:10]<='2022-09-19')]
 pd.DataFrame(trades).to_csv(O/'ALL_PVR_SELL_REFERENCE_BRIDGES.csv',index=False);pd.DataFrame(parts).to_csv(O/'SELL_PART_COST_BRIDGES.csv',index=False);pd.DataFrame(groups).to_csv(O/'FINAL_REASON_SUMMARY.csv',index=False);pd.DataFrame(rounds).to_csv(O/'COMPLETE_ROUND_REFERENCE_BRIDGES.csv',index=False);save('EXAMPLES.json',examples)
 summary=dict(status='PASS_POSTHOC_REFERENCE_BRIDGES',account_runs=0,all_sell_fills=len(trades),unknown_prior_references=sum(not r['reference_known']for r in trades),corporate_action_adjusted_sells=sum(bool(r['actions_between'])for r in trades),losing_rounds=loss_summary,final_reason_groups=groups,source_sha256=source,limitations=['Previous actual observed eligible close strictly precedes sale day; synthetic rows excluded; intervening corporate actions translated via original signal cash/split terms, assumed preknown.','Reference bridges keep actual sell quantities and actual allocated buy basis, and do not assert preceding-close execution was possible.','Round reference sum combines each sold tranche at its own preceding close; it is not a single-time whole-round portfolio mark or causal stop-loss attribution.','5bp and sell fees are already included in actual PnL, never deducted twice.','No post-sale prices, no rerun, no modified orders or model. Fixed future pool and unknown halt/limit tradability remain.'])
 save('SUMMARY.json',summary);save('SOURCE_SHA256.json',source);save('OUTPUT_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(dict(losing_rounds=loss_summary,reasons=groups,examples=examples),default=str,indent=2),flush=True)
if __name__=='__main__':main()
