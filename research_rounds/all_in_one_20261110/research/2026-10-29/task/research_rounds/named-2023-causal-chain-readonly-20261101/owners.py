"""Read-only allocation-journal walk. Applies only already recorded quantities/orders.
No Account/Contract instance, admission/strategy method, or hypothetical trade is run.
"""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,collections,time,traceback,copy
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;Y=W/'recovery-2023-readiness-20261101';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');NAMES=['300308.SZ','300502.SZ']
sys.path.insert(0,str(W/'c1-drawdown-capacity-20261101'));import adapter_c1 as C
J=C.J
def read(p):return json.loads(Path(p).read_text())
def stream(p):
 with gzip.open(p,'rt') as f:
  for s in f:yield json.loads(s)
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(name,x):
 # Preserve the accounting evidence before strict JSON; unavailable numeric
 # context is null, never silently zero and never used to repair resource gaps.
 C.IO.write_pickle((O/name).with_suffix('.raw.pkl'),x)
 C.IO.write_json(O/name,J.T.norm(J.W.canon(x)))
def day(x):return str(x)[:10]
M=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json');SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};FF={}
def facts(sid):
 if sid not in FF:FF[sid]=pd.read_parquet(SM[sid]['refs']['facts'],columns=['factor','i_target','g_grade','raw_close'])
 return FF[sid]
def row(sid,d):
 f=facts(sid);i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0;return f.iloc[i]
def main():
 started=time.monotonic();fixed=read(W/'universe-cp1-inputs-20261031/FREEZE.json')['stocks']
 # Immutable original price/rule access only; context constructs no account.
 t=time.monotonic();_,market,_=J.M.context('2023-12-29',ids=fixed);print('READONLY_NATIVE_MARKET',round(time.monotonic()-t,3),flush=True)
 h=np.load(J.M.P/'h1.npz');dates=pd.DatetimeIndex(h['dates']);mask=(dates>='2023-01-01')&(dates<='2023-12-31');scores=pd.DataFrame(h['score'][mask],index=dates[mask],columns=[str(s) for s in h['symbols']]);states={x['series']:pd.read_parquet(x['refs']['state']).set_index('day').to_dict('index') for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 reports=[]
 for ref in ['Bdiag','C1']:
  root=Y/'runs'/ref/'pair';b=book(root/'B.json.gz');ds={day(x['at']):x for x in stream(root/'daily.jsonl.gz')};dd=sorted(ds);caps=[x for x in stream(root/'capacity-checks.jsonl.gz') if day(x['at']).startswith('2023')];byday=collections.defaultdict(list)
  for seq,x in enumerate(caps):x['trace_sequence']=seq;byday[day(x['at'])].append(x)
  intents={(i['sid'],day(x['at']),i['role']):i for x in b['decisions'] if day(x['at']).startswith('2023') for i in x['intents']};audit_reserve={x['order_id']:x for x in b['audit'] if x['kind']=='reserve'}
  reserved={x['budget_order']:x for x in b['journal'] if x['kind']=='real_reserve'};journal_byday=collections.defaultdict(list)
  for x in b['journal']:
   if day(x.get('at','')).startswith('2023'):journal_byday[day(x['at'])].append(x)
  target_days={d for d,rs in byday.items() if any(x['sid'] in NAMES for x in rs)};out=[];fail=[];checks=0
  for d in sorted(target_days):
   p=dd[dd.index(d)-1];prev=ds[p];at=J.M.N.iso(d+'T09:30:00+08:00');lots=copy.deepcopy(prev['layers']);pending=[];unknown=[]
   if float(prev['order_reserved'])!=0:unknown.append('prior closing actual buy reservations require additional saved remainder lineage')
   # Actual corporate-action quantity changes before this open only.
   for e in b['journal']:
    if e['kind']!='actual_split' or not (p<day(e['at'])<=d):continue
    for l in lots:
     if l['sid']==e['sid']:
      exact=D(l['qty'])*D(str(e['ratio']))
      if exact!=int(exact):unknown.append('fractional split allocation needs original per-layer remainder; not guessed')
      l['qty']=int(exact);l['unit_cost']=float(l['unit_cost'])/float(e['ratio'])
   # Real sales happen before every opening funding decision. No expected sale credit.
   for e in journal_byday[d]:
    if e['kind']!='real_sell_fill':continue
    for part in e['parts']:
     l=next((x for x in lots if x['id']==part['layer']),None)
     if l is None:unknown.append('sale layer absent from prior close')
     else:l['qty']-=part['shares'];assert l['qty']>=0
   lots=[l for l in lots if l['qty']>0]
   marks=market.marks(at,{l['sid'] for l in lots})
   for l in lots:
    factor=D(str(row(l['sid'],d).factor));line=D(str(l['last_core_line'] if l['role']=='core' else l['floor']));l['_mark']=float(marks[l['sid']].cny_price(at));l['_rawfloor']=float(line/factor)
   for x in byday[d]:
    sid=x['sid'];sec=M[sid]['sector_id'];signal=day(x['decision_at']);i=intents.get((sid,signal,x['role']))
    # This flag records an ACTUAL successful migration at this exact call.
    if x['role']=='mobile' and x['confirmed_migration_admitted']:
     for l in lots:
      if l['sector']==sec and l['attempt']==x['attempt'] and l['pool']=='probe':l['pool']='confirmed'
    owners=[]
    if sid in NAMES:
     for l in lots:
      fr=row(l['sid'],signal);st=states[l['sector']].get(signal,{});sc=scores.loc[pd.Timestamp(signal),l['sid']] if pd.Timestamp(signal) in scores.index else np.nan
      owners.append(dict(owner_type='actual_held_layer',layer=l['id'],sid=l['sid'],name=M[l['sid']]['name'],sector=l['sector'],pool=l['pool'],role=l['role'],attempt=l['attempt'],qty=l['qty'],mark=l['_mark'],raw_protection=l['_rawfloor'],unit_cost=l['unit_cost'],capital=l['qty']*l['_mark'],risk=l['qty']*max(0.,l['_mark']-l['_rawfloor']),gross_price_unrealized=l['qty']*(l['_mark']-float(l['unit_cost'])),last_decision_I_valid=bool(fr.i_target),last_decision_G1_grade=float(fr.g_grade) if pd.notna(fr.g_grade) else None,last_decision_H1=float(sc) if pd.notna(sc) else None,last_decision_market_stage=st.get('stage_name'),market_attempt=st.get('attempt_id'),source='prior close real lot, actual split/sell quantities, original known-open mark and prior-known protection; gross price PnL excludes fees/dividends'))
     owners+=copy.deepcopy(pending)
     def sums(pool=None,sector=None):
      rs=[o for o in owners if (pool is None or o['pool']==pool) and (sector is None or o['sector']==sector)];return sum(o['capital'] for o in rs),sum(o['risk'] for o in rs)
     sc,sr=sums(sector=sec);_,ar=sums();reserve=sum(o['capital']+o['fee_reserved'] for o in pending);fees=sum(o['fee_reserved'] for o in pending);gaps={}
     for rr in x['routes']:
      pc,pr=sums(pool=rr['pool'])
      for k,a,z in [('pool_capital',pc,rr['pool_capital']),('pool_risk',pr,rr['pool_risk']),('sector_capital',sc,rr['sector_capital']),('sector_risk',sr,rr['sector_risk']),('all_risk',ar,rr['all_risk']),('reserve',reserve,rr['reserve']),('pending_fees',fees,rr['pending_fees'])]:gaps[rr['pool']+':'+k]=a-z
     exact=not unknown and all(abs(v)<1e-6 for v in gaps.values());checks+=1
     binding={}
     for rr in x['routes']:
      for reason in rr['minimum_reasons']:
       dim='risk' if reason in ['probe_risk','sector_risk','account_risk'] else 'capital';pool=rr['pool'] if reason in ['pool_capital','probe_risk'] else None;sector=sec if reason in ['sector_capital','sector_risk'] else None
       subset=[o for o in owners if (pool is None or o['pool']==pool) and (sector is None or o['sector']==sector) and (reason!='stock_capital' or o['sid']==sid)]
       if reason=='cash_or_original_reserve':subset=pending
       ordered=sorted(subset,key=lambda o:(-o[dim],o['sid'],str(o.get('layer',o.get('budget_order')))))
       binding[rr['pool']+':'+reason]=dict(measure=dim,total=sum(o[dim] for o in subset),owners=len(subset),held=sum(o[dim] for o in subset if o['owner_type']=='actual_held_layer'),same_open_reserved=sum(o[dim] for o in subset if o['owner_type']=='same_open_reserved_order'),top10=ordered[:10],remaining_after_top10=sum(o[dim] for o in ordered[10:]))
     out.append(dict(policy=ref,sid=sid,at=x['at'],signal_day=signal,role=x['role'],trace_sequence=x['trace_sequence'],recorded_route=x,reconstruction_exact=exact,component_gaps=gaps,unknown=sorted(set(unknown)),previous_closing_day=p,current_known_open_mark_source='unchanged native market.latest_mark; no same-day close used',holdings_layer_count=len(lots),earlier_same_open_reserved_orders=len(pending),actual_available_cash_view=x['cash']-reserve,original_retained_cash=.1*float(x['decision_NAV']),binding_owners=binding,local_relaxed_preview=None))
     if not exact:fail.append(dict(sid=sid,at=x['at'],role=x['role'],gaps=gaps,unknown=sorted(set(unknown))))
    if x['selected_quantity']:
     bid=f"B|{x['decision_at'].replace(' ','T')}|{sid}|{x['role']}";j=reserved.get(bid)
     if j is None:
      # Use exact saved order lineage, never fabricate a reserve.
      j=next((v for v in reserved.values() if day(v['at'])==d and v['sid']==sid and v['role']==x['role'] and day(v['budget_order'].split('|')[1])==signal),None)
     if j is None:unknown.append('accepted route lacks saved native reservation');continue
     a=audit_reserve[j['order']];assert a['target_shares']==j['shares']==x['selected_quantity'];assert i is not None
     q=j['shares'];price=float(j['price']);floor=float(D(i['floor'])/D(str(row(sid,d).factor)));fee=float(a['fee_reserved_cny']);assert abs(q*price-float(a['gross_budget_cny']))<1e-6
     pending.append(dict(owner_type='same_open_reserved_order',budget_order=j['budget_order'],native_order=j['order'],sid=sid,name=M[sid]['name'],sector=sec,pool=j['pool'],role=j['role'],attempt=x['attempt'],qty=q,mark=price,raw_protection=floor,capital=q*price,risk=q*max(0.,price-floor),fee_reserved=fee,original_priority_rank=i['rank'],original_H1=i['score'],route_sequence=x['trace_sequence'],posthoc_had_fill=any(z['kind']=='real_buy_fill' and z.get('budget_order')==j['budget_order'] for z in journal_byday[d]),source='actual earlier native reserve; same opening fills occur only after all funding decisions'))
   if len(out)%20==0:print('OWNERS_PROGRESS',ref,len(out),flush=True)
  save(ref+'/OWNERS_SNAPSHOTS.json',out);save(ref+'/OWNERS_GAPS.json',fail);reports.append(dict(policy=ref,snapshots=len(out),exact=sum(x['reconstruction_exact'] for x in out),unknown_or_mismatched=len(fail),original_source_totals_never_repaired=True));print('OWNERS_RESULT',reports[-1],flush=True)
 save('OWNERS_COMPLETION.json',dict(reports=reports,new_accounts=0,account_strategy_calls=0,accounting_uses_only_observed_journal_actions=True,seconds=time.monotonic()-started));print('OWNERS_DONE',round(time.monotonic()-started,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('OWNERS_ERROR.json',dict(reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
