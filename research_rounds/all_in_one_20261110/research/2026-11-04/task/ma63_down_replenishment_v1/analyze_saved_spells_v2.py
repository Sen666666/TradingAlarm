"""Bounded saved-native attribution only; no new account, cash/CA/basis engine."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import argparse,gzip,hashlib,importlib.util,json,datetime
getcontext().prec=80
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
AX=T/'risk_constraints/ma63_exposure_axis_v1/DAILY_ALIGNED.json'
H_PATH=T/'capacity_cost_guard_analysis_v1/analyze_completed_v1.py'
ORIGINAL=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/c1-drawdown-capacity-20261101/analyze_saved.py')
GOLD=T/'capacity_cost_guard_v1/runs/long-v1/arms/B'
ACTION=T/'loss_correction/ma63_buy_chain_v1/ALL_1557_ROWS.json'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def n(x):return D(str(x))
def gz(p):
 with gzip.open(p,'rt')as f:return json.load(f)
def load_helpers():
 s=importlib.util.spec_from_file_location('existing_saved_fixed_phase_helpers',H_PATH);h=importlib.util.module_from_spec(s);s.loader.exec_module(h);return h
def freeze():
 assert not(O/'INPUT_FREEZE.json').exists(),'do not overwrite protocol/source freeze'
 axis=[r for r in read(AX)if r['arm']=='NO60'];assert len(axis)==484
 spells=[];cur=None
 for ix,r in enumerate(axis):
  down=r['prior_benchmark_CLOSE']['axis_slope']=='below_down'
  if down:
   assert r['prior_benchmark_CLOSE']['day']<r['day']
   if cur is None:
    cur=dict(spell_id=f'DOWN_{len(spells)+1:02d}',first_axis_index=ix,previous_close=axis[ix-1]['day']if ix else None,days=[]);spells.append(cur)
   cur['days'].append(r['day']);cur['last_axis_index']=ix
  else:cur=None
 assert sum(len(x['days'])for x in spells)==298
 if (O/'ALL_SPELLS_FROZEN.json').exists():assert read(O/'ALL_SPELLS_FROZEN.json')==spells
 else:save('ALL_SPELLS_FROZEN.json',spells)
 protocol='''FROZEN BEFORE ATTRIBUTION. Only NO60, 2022–23 original 484-day execution calendar.
DOWN uses prior_benchmark_CLOSE.axis_slope == below_down. Maximal contiguous runs in
the complete original calendar, not compressed filtered dates. All zero/positive spells stay.
Use reviewed saved reporting H.account and H.after924 layer-boundary method, not generic
audit reader as a period API. A.price is the same existing original causal raw-close lookup.
Layer boundary W = native cumulative cash + native booked dividend + actual qty * original
mark while live; already-closed layer uses original saved final cash/dividend; future layer W=0.
Period wealth = W(end CLOSE)-W(previous CLOSE). Sum all layers to native NAV difference.
Carry group consists of actual live layers at prior CLOSE, plus any native already-closed
claim whose unchanged cumulative booked dividend/cash cannot create new wealth on payment.
New group consists only of layers with actual buy fill in this spell. No decision-cohort lifetime
PnL substitution. Native AR payment only transfers liquid accounts; no new booked dividend.
Actual new fills may originate from previously committed orders/partial orders: the new-fill
group is interval attribution, not proof every fill was then cancelable or could be blocked.
Per-spell old/new positive, negative and zero rows all saved. Full-spell sum must match exact
source 298-day wealth. No deletion NAV, q sizing, market allowance, new recovery, new account,
CA reconstruction, acquisition basis, fee model or cash engine. First-sell before/after buys
use native trade-list ordering (even same timestamp); no claim of one-to-one sale financing.
Actual current gold is the independently exact audited No60 B full continuous 726-day view.
Only 2022–23 DOWN spells attributed. No future labels or 2024 results select spell membership.
'''
 (O/'PROTOCOL.txt').write_text(protocol)
 b=gz(GOLD/'pair/B.json.gz');h=load_helpers()
 sources=[AX,H_PATH,ORIGINAL,ACTION,GOLD/'pair/B.json.gz',GOLD/'pair/daily.jsonl.gz',GOLD/'pair/balances.jsonl.gz',O/'PROTOCOL.txt',O/'ALL_SPELLS_FROZEN.json',Path(__file__)]
 sources += [Path(h.A.SM[s]['refs']['facts'])for s in sorted({t['security_id']for t in b['trades']})]
 save('INPUT_FREEZE.json',dict(before_attribution=True,at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256={str(p.resolve()):sha(p)for p in sources},selected_execution_days=298,spells=len(spells),source_exact_wealth=sum((n(r['wealth_change'])for r in axis if r['prior_benchmark_CLOSE']['axis_slope']=='below_down'),Z),new_accounts=0))
 save('ORIGIN.json',dict(saved_reader=str(ORIGINAL),saved_reader_sha256=sha(ORIGINAL),functions={'account':'original analyze_saved.py:40–78; expected-day parameterization already audited in H','boundary':'H.after924:84–97, reused at both native CLOSE endpoints','flows':'H.flow_daily:26–41 and H.period:43–48'},helpers=str(H_PATH),helpers_sha256=sha(H_PATH),generic_audit_reader_not_claimed_as_period_API=True))
 print('FROZEN',len(spells),'spells',sum(len(x['days'])for x in spells),'days',flush=True)
def analyze():
 v2=read(O/'ROUNDING_ADDENDUM_V2.json');assert sha(__file__)==v2['new_reporter_sha256'];freeze=read(O/'INPUT_FREEZE.json');assert all(sha(p)==s for p,s in freeze['source_sha256'].items())
 h=load_helpers();h.A.O=O;a=h.account('long','NO60_gold',GOLD,726)
 axis={r['day']:r for r in read(AX)if r['arm']=='NO60'};byday=a['byday'];layers={l['layer']:l for l in a['layers']};final={l['id']:l for l in a['book']['layers']};actions={x['layer']:x['action']for x in read(ACTION)}
 flows={r['day']:r for r in h.flow_daily(a)};tx=a['book']['trades'];bounds={};out=[];layerrows=[];EPS=D('.000001')
 def boundary(day):
  if day in bounds:return bounds[day]
  live={x['id']:x for x in byday[day]['layers']}if day else {};w={}
  for lid,l in layers.items():
   if day is None or str(l['opened'])[:10]>day:v=Z
   elif lid in live:
    x=live[lid];v=n(x['cash'])+n(x['dividend'])+D(x['qty'])*h.A.price(l['sid'],day)
   else:
    f=final[lid];assert f['qty']==0 and f['closed'] and str(f['closed'])[:10]<=day,('missing_live_layer',day,lid)
    v=n(f['cash'])+n(f['dividend'])
   w[lid]=v
  expected=n(byday[day]['nav'])-D(1000000)if day else Z
  assert abs(sum(w.values(),Z)-expected)<=EPS,('boundary_native_wealth',day,sum(w.values(),Z)-expected)
  bounds[day]=(w,live);return w,live
 def group(rr):
  return dict(layers=len(rr),positive_layers=sum(x['period_wealth']>0 for x in rr),negative_layers=sum(x['period_wealth']<0 for x in rr),zero_layers=sum(x['period_wealth']==0 for x in rr),wealth=sum((x['period_wealth']for x in rr),Z),positive_wealth=sum((x['period_wealth']for x in rr if x['period_wealth']>0),Z),negative_wealth=sum((x['period_wealth']for x in rr if x['period_wealth']<0),Z))
 for s in read(O/'ALL_SPELLS_FROZEN.json'):
  lo,hi=s['days'][0],s['days'][-1];w0,live0=boundary(s['previous_close']);w1,live1=boundary(hi)
  trades=[t for t in tx if lo<=str(t['at'])[:10]<=hi];new={t['layer']for t in trades if t['side']=='buy'};assert not(new&set(live0))
  rows=[]
  for lid in sorted(set(live0)|new):
   l=layers[lid];r=dict(spell_id=s['spell_id'],layer=lid,sid=l['sid'],role=l['role'],opened=l['opened'],group='new_actual_fill_in_spell'if lid in new else'carry_at_previous_CLOSE',action=actions.get(lid,'UNKNOWN'),boundary_wealth=w0[lid],end_wealth=w1[lid],period_wealth=w1[lid]-w0[lid],qty_at_boundary=live0.get(lid,{}).get('qty',0),qty_at_end=live1.get(lid,{}).get('qty',0));rows.append(r)
  excluded=set(layers)-set(live0)-new;assert all(w1[i]==w0[i]for i in excluded),('unattributed_closed_claim_change',s['spell_id'])
  original=sum((n(axis[d]['wealth_change'])for d in s['days']),Z);actual=n(byday[hi]['nav'])-(n(byday[s['previous_close']]['nav'])if s['previous_close']else D(1000000));layer_total=sum((r['period_wealth']for r in rows),Z);residual=original-layer_total;assert abs(residual)<=EPS and original==actual
  rr=[flows[d]for d in s['days']];period=h.period(rr);assert abs(n(period['wealth_change'])-original)<=EPS
  firstsell=next((i for i,t in enumerate(trades)if t['side']=='sell'),None)
  buycash=lambda tt:sum((n(t['gross_cny'])+n(t['fees_cny'])for t in tt if t['side']=='buy'),Z)
  out.append(dict(**s,start=lo,end=hi,original_period_wealth=original,rounding_residual=residual,actual_flow_wealth_residual=original-n(period['wealth_change']),old=group([r for r in rows if r['group']=='carry_at_previous_CLOSE']),new=group([r for r in rows if r['group']=='new_actual_fill_in_spell']),new_action={k:group([r for r in rows if r['group']=='new_actual_fill_in_spell'and r['action']==k])for k in sorted({r['action']for r in rows if r['group']=='new_actual_fill_in_spell'})},actual_trade_period=period,inventory_begin=axis[lo]['lag_inventory'],inventory_end=axis[hi]['inventory'],NAV_begin=axis[lo]['lag_NAV'],NAV_end=axis[hi]['NAV'],exposure_begin_pct=axis[lo]['lag_exposure_pct'],exposure_end_pct=axis[hi]['exposure_pct'],nominal_begin=axis[lo]['lag_nominal_risk'],nominal_end=axis[hi]['nominal_risk'],first_sell_at=trades[firstsell]['at']if firstsell is not None else None,buy_cash_before_first_sell=buycash(trades[:firstsell])if firstsell is not None else buycash(trades),buy_cash_after_first_sell=buycash(trades[firstsell+1:])if firstsell is not None else Z,first_sell_split_scope='native trade list order, not financing causation',money_bridge_including_explicit_rounding_exact=True,layer_bridge_within_existing_reader_EPS=True));layerrows+=rows
  print('SPELL',s['spell_id'],lo,hi,'wealth',original,'old',out[-1]['old']['wealth'],'new',out[-1]['new']['wealth'],flush=True)
 save('ALL_SPELL_RESULTS.json',out);save('ALL_LAYER_PERIOD_WEALTH.json',layerrows)
 total=sum((x['original_period_wealth']for x in out),Z);assert total==n(freeze['source_exact_wealth'])
 old=group([x for x in layerrows if x['group']=='carry_at_previous_CLOSE']);new=group([x for x in layerrows if x['group']=='new_actual_fill_in_spell'])
 rounding=sum((x['rounding_residual']for x in out),Z);assert old['wealth']+new['wealth']+rounding==total and abs(rounding)<=EPS
 summary=dict(status='PRODUCER_COMPLETE_INDEPENDENT_REVIEW_PENDING',days=298,spells=len(out),exact_source_wealth=total,rounding_residual=rounding,max_abs_spell_rounding=max(abs(x['rounding_residual'])for x in out),existing_reader_EPS=EPS,old=old,new=new,positive_spells=sum(x['original_period_wealth']>0 for x in out),negative_spells=sum(x['original_period_wealth']<0 for x in out),zero_wealth_spells=sum(x['original_period_wealth']==0 for x in out),zero_inventory_entire_spell=sum(all(n(axis[d]['lag_inventory'])==0 and n(axis[d]['inventory'])==0 for d in x['days'])for x in out),source_post_exact=all(sha(p)==v for p,v in freeze['source_sha256'].items()),new_accounts=0,not_avoidable_loss_or_sale_financing=True)
 assert summary['source_post_exact'];save('SUMMARY.json',summary);save('COMPLETED.json',summary);print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','analyze']);args=p.parse_args()
 try:freeze()if args.mode=='freeze'else analyze()
 except BaseException as e:save('FAILURE_v2_'+args.mode+'.json',dict(type=type(e).__name__,reason=str(e)));raise
