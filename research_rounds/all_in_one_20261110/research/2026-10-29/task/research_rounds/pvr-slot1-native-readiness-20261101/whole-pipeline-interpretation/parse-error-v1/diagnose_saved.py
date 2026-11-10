"""Bounded saved-ledger interpretation. No account, model, or new indicator."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,hashlib,sys
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;W=P.parent;Z=D(0)
sys.path.insert(0,str(P));import analyze_results as A
SM={r['symbol']:r for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
IM=json.loads((W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json').read_text())
F={};CP={};SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if x is None:return None
 if not isinstance(x,(str,bool,D)):
  try:
   if pd.isna(x):return None
  except (TypeError,ValueError):pass
 return x.item() if hasattr(x,'item') else x
def save(p,x):
 p=O/p;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def facts(sid):
 if sid not in F:
  p=Path(SM[sid]['refs']['facts']);assert sha(p)==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p);F[sid]=pd.read_parquet(p)
 return F[sid]
def state(sid,d,cp=False):
 f=facts(sid);t=pd.Timestamp(d)
 if t not in f.index:return dict(day=d,observed=False,reason='no exact source observation; no breadth/feature forward fill')
 r=f.loc[t];out=dict(day=d,observed=True,**{k:r[k] for k in ['close','raw_close','factor','i_target','i_buy','i_floor','e0_target','e0_floor','g_grade','g_ready','g_fresh_up','g_acute_down']})
 if cp:
  if sid not in CP:
   p=Path(SM[sid]['refs']['CP1']);assert sha(p)==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p);CP[sid]=pd.read_parquet(p)
  if t in CP[sid].index:
   z=CP[sid].loc[t];out['CP1']={k:z[k] for k in ['receipt','candidate','phase','anchor','frontier','credit','displacement','reset_reason']}
 return clean(out)
def aggregate(ls):return A.M.contribution(ls)

def main():
 comparisons=read(P/'COMPARISON.json');decomp=[];risk_summary={};entry_groups={};cases=[]
 for win in ['2022','2025_26']:
  for ref in ['SC','PVR_SLOT1']:
   root=(W/('2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031')/'runs/B_diag') if ref=='SC' else P/'runs'/win
   b=book(root/'pair/B.json.gz');ds=rows(root/'pair/daily.jsonl.gz');dd={day(r['at']):r for r in ds};dates=list(dd)
   layers=read(P/'analysis'/win/ref/'LAYERS.json');ls={x['layer']:x for x in layers};end=dates[-1]
   op=[x for x in b['layers'] if x['qty']];partial=[x['id'] for x in op if any(t['side']=='sell' and any(y['layer']==x['id'] for y in t.get('parts',[])) for t in b['trades'])]
   assert not partial,'partial-open basis allocation would need separate documented convention'
   closed_cash=sum((n(x['cash']) for x in b['layers'] if not x['qty']),Z)
   div=sum((n(x['dividend']) for x in b['layers']),Z);opdiv=sum((n(x['dividend']) for x in op),Z)
   open_mark_to_cost=sum((n(x['cash'])+D(x['qty'])*A.A.price(x['sid'],end) for x in op),Z)
   unpaid=n(ds[-1]['dividend_receivable']);paid=div-unpaid
   assert abs(closed_cash+open_mark_to_cost+div-(n(b['ending_NAV'])-D(1000000)))<D('.00000001')
   decomp.append(dict(window=win,reference=ref,closed_trading_cash_net_excluding_dividends=closed_cash,
    unrealized_price_net_after_original_buy_fees=open_mark_to_cost,dividend_recognized=div,
    dividends_paid=paid,dividend_receivable=unpaid,open_layer_dividends=opdiv,
    open_layers_with_partial_sales=0,open_layer_contribution=open_mark_to_cost+opdiv,
    price_or_cash_reconciliation=Z,not_external_mark_or_tax_basis_certification=True))
   if win!='2022':continue
   funded=read(P/'analysis'/win/ref/'FUNDED_RANK_STAGE_CHAIN.json');action={r['layer']:r['action'] for r in read(P/'analysis'/win/ref/'ENTRY_ACTIONS.json')}
   by=collections.defaultdict(list)
   for r in funded:
    l=ls[r['layer']];s=state(l['sid'],l['signal_day']);g='unknown' if not s['observed'] or not s['g_ready'] else 'warm' if s['g_grade']>=2 else 'below_warm'
    for kind,value in [('action',action[l['layer']]),('industry_stage',r['market_industry_stage']),('current_G1',g),('role_pool',l['role']+'_'+l['pool_at_fill'])]:by[kind,str(value)].append(l)
   entry_groups[ref]={kind:{v:aggregate(vv) for (k,v),vv in by.items() if k==kind} for kind in ['action','industry_stage','current_G1','role_pool']}
   rs=[]
   for d,r in dd.items():
    groups=collections.defaultdict(lambda:[Z,Z,Z,Z,0]);total_pr=total_gr=Z
    for x in r['layers']:
     sid=x['sid'];f=facts(sid);t=pd.Timestamp(d);assert t in f.index,(sid,d,'exact held factor/close unknown')
     z=f.loc[t];mark=n(z.raw_close);cost=n(x['unit_cost']);q=D(x['qty'])
     line=n(x['last_core_line']) if x['role']=='core' else n(x['floor']);floor=line/n(z.factor)
     principal=q*max(min(mark,cost)-floor,Z);giveback=q*max(mark-max(cost,floor),Z)
     assert abs(principal+giveback-q*max(mark-floor,Z))<D('.000001')
     total_pr+=principal;total_gr+=giveback
     tag='exit_pending' if sid in r['pending_sells'] else 'I_invalid_no_exit_unknown' if not bool(z.i_target) else 'I_valid_G1_below_warm' if bool(z.g_ready) and z.g_grade<2 else 'I_valid_G1_warm_or_not_ready'
     for k in ['all',tag,'role_'+x['role']]:
      v=groups[k];v[0]+=q*mark;v[1]+=principal;v[2]+=giveback;v[3]+=q*mark if mark<=floor else Z;v[4]+=1
    original=n(r['pool_probe'][1])+n(r['pool_confirmed'][1]);residual=original-total_pr-total_gr
    assert abs(residual)<D('.01'),(ref,d,'pending risk or units need explicit bridge',residual)
    rs.append(dict(day=d,NAV=r['nav'],principal=total_pr,profit_giveback=total_gr,
      nominal_risk=total_pr+total_gr,groups=dict(groups),risk_bridge_difference=residual))
   totalrisk=sum((r['nominal_risk'] for r in rs),Z)
   risk_summary[ref]=dict(unit='sum of daily close lot risk amounts; correlated lot-days, not independent observations',
    mean_principal=sum((r['principal'] for r in rs),Z)/len(rs),mean_profit_giveback=sum((r['profit_giveback'] for r in rs),Z)/len(rs),
    principal_share_of_risk_days=sum((r['principal'] for r in rs),Z)/totalrisk,
    mean_capital_by_state={k:sum((r['groups'].get(k,[Z]*5)[0] for r in rs),Z)/len(rs) for k in ['exit_pending','I_valid_G1_below_warm','I_valid_G1_warm_or_not_ready']},
    risk_by_state={k:sum((sum(r['groups'].get(k,[Z]*5)[1:3],Z) for r in rs),Z)/totalrisk for k in ['exit_pending','I_valid_G1_below_warm','I_valid_G1_warm_or_not_ready']},
    source_clock='close AFTER original planning; not reconstructed exact pre-open resource state')
   save(Path('risk2022')/(ref+'.json'),rs)
   worst=read(P/'analysis'/win/ref/'DETERMINISTIC_WORST3_CLOSED_STOCKS.json')
   for chosen in worst:
    sid=chosen['sid'];loser=min((l for l in layers if l['sid']==sid and not l['qty']),key=lambda l:(n(l['net']),l['layer']))
    lid=loser['layer'];req=next(x for x in read(P/'analysis'/win/ref/'EXITS.json') if x['layer']==lid)
    rd=day(req['request_at']);j=dates.index(rd);prior=dd[dates[j-1]] if j else None
    old=next((x for x in prior['layers'] if x['id']==lid),None) if prior else None
    line=old['last_core_line'] if old and old['role']=='core' else old['floor'] if old else None
    chain=[r for r in funded if r['sid']==sid]
    cases.append(dict(reference=ref,selection='three stocks with most negative sum of fully-closed layer contribution; then worst closed layer within each',
      stock=chosen,selected_layer=loser,entry_signal=state(sid,loser['signal_day'],True),
      exit_request=req,request_day_source=state(sid,rd,True),previous_close_known_line_adjusted=line,
      first_sell_trade=next((t for t in b['trades'] if t['side']=='sell' and any(p['layer']==lid for p in t['parts'])),None),
      all_actual_buy_chain=chain))
   pause=next(x for x in b['audit'] if x['kind']=='risk_checkpoint' and x.get('event')=='pause');resume=next(x for x in b['audit'] if x['kind']=='risk_checkpoint' and x.get('event')=='resume')
   flat=next((d for d in dates if day(pause['at'])<=d<=day(resume['at']) and not dd[d]['positions']),None)
   save(Path('ACT2022')/(ref+'.json'),dict(first_pause=pause,first_flat_after_pause=flat,first_resume=resume,
     end_state=dict(day=end,on=ds[-1]['on'],NAV=ds[-1]['nav'],inventory=ds[-1]['inventory'],available=ds[-1]['available']),
     quarters=read(P/'analysis'/win/ref/'METRICS.json')['quarters']))
 save('REALIZED_UNREALIZED_BRIDGE.json',decomp);save('2022_ENTRY_GROUPS.json',entry_groups)
 save('2022_HELD_RISK_SUMMARY.json',risk_summary);save('2022_DETERMINISTIC_FAILURE_CHAINS.json',cases)
 # Fixed calendar quarters describe hindsight prices only, not an actionable regime switch.
 market=[]
 for lo,hi in [('2022-01-01','2022-03-31'),('2022-04-01','2022-06-30'),('2022-07-01','2022-09-30'),('2022-10-01','2022-12-30')]:
  rr=[]
  for r in IM:
   p=Path(r['refs']['CP1_input']);SRC[str(p)]=sha(p);f=pd.read_parquet(p,columns=['close'])
   before=f.loc[f.index<pd.Timestamp(lo)];end=f.loc[f.index<=pd.Timestamp(hi)]
   if len(before) and len(end):rr.append(float(end.close.iloc[-1]/before.close.iloc[-1]-1)*100)
  market.append(dict(window=[lo,hi],industries=len(rr),positive=sum(v>0 for v in rr),median_pct=float(pd.Series(rr).median()),q25_pct=float(pd.Series(rr).quantile(.25)),q75_pct=float(pd.Series(rr).quantile(.75))))
 save('2022_FIXED_QUARTER_PRICE_ENVIRONMENT.json',market);save('SOURCE_SHA256.json',SRC)
 print('DECOMPOSITION',decomp,flush=True);print('RISK2022',risk_summary,flush=True)
 print('FAILURES',[(x['reference'],x['selected_layer']['name'],x['entry_signal'].get('g_grade'),x['exit_request']['reason'],x['exit_request']['request_at'],x['exit_request']['first_actual_sell']) for x in cases],flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),account_replays=0));raise
