"""All original CP first-proposal price/unit bounds; not an execution policy."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,hashlib,json,pickle,statistics,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent.parent/'task';B=Path('/Users/bytedance/Documents/ChatGPT/money');SOURCES={};Z=D(0)
def bind(p):p=Path(p);SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def stats(a):return dict(n=len(a),minimum=min(a)if a else None,median=statistics.median(a)if a else None,maximum=max(a)if a else None)
def eff(vs,day):
 a=[r for r in vs if r['from']<=day and(r.get('to')is None or day<r['to'])];assert len(a)==1;return a[0]['rule']

def main():
 start=time.monotonic();bind(__file__);bind(O/'CP_TAIL_STATIC_CARD.txt')
 with bind(O/'PRICE_FEATURES.pkl').open('rb')as h:features=pickle.load(h)
 sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 rules=read(B/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 cfg={
 'long':(T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',T/'risk_constraints/continuation2024_finance/analysis/2022_2024/PVR_NO_CONFIRMED60/LAYERS.json'),
 'strong':(T/'pvr_pool_feasibility/runs/2025_26/pair',T/'loss_correction/pvr_no60_2025_26/analysis/2025_26/PVR_NO60/LAYERS.json')}
 fixed25=read(O.parent/'POST_PURCHASE_ALL25_PATHS.json');fixed_ids={r['layer']for r in fixed25};assert len(fixed_ids)==25
 cache={};rows=[];mothers={}
 for window,(root,lp)in cfg.items():
  b=load(root/'B.json.gz');ds=load(root/'daily.jsonl.gz',True);daily={r['at'][:10]:r for r in ds};days=sorted(daily)
  ll={r['layer']:r for r in read(lp)};buys={t['layer']:t for t in b['trades']if t['side']=='buy'}
  first={};first_ix={}
  for ix,e in enumerate(b['audit']):
   if e['kind']=='pilot_layer_exit':
    for lid in e['layers']:
     if lid not in first:first[lid]=e;first_ix[lid]=ix
  mobile={l['id']for l in b['layers']if l['kind']=='add'}
  mothers[window]=dict(all_mobile_layers=len(mobile),first_exit_proposals=sum(lid in first for lid in mobile),
   first_exit_reason_counts=dict(Counter(first[lid]['reason']for lid in mobile if lid in first)))
  if window=='strong':
   mothers[window]['fixed_H1_25_all_roles']=[dict(layer=r['layer'],sid=r['sid'],role=r['role'],original_net=r['net'],
    first_exit_reason=first[r['layer']]['reason']if r['layer']in first else None,
    included_first_CP_proposal=r['layer']in first and first[r['layer']]['reason']=='CP1_add_protection')for r in fixed25]
  for lid,e in first.items():
   if lid not in mobile or e['reason']!='CP1_add_protection':continue
   assert time.monotonic()-start<60,'frozen bound budget exhausted'
   d=e['at'][:10];sid=e['sid'];rec=daily[d];native=next((l for l in rec['layers']if l['id']==lid),None)
   assert native is not None,'first CP request must still have actual quantity at its CLOSE'
   if sid not in cache:
    p=Path(sm[sid]['refs']['facts']);assert hashlib.sha256(p.read_bytes()).hexdigest()==sm[sid]['output_sha256'][str(p)]
    cache[sid]=pd.read_parquet(bind(p),columns=['close','factor','segment_id','i_target','i_floor','e0_target'])
   f=cache[sid];dt=pd.Timestamp(d);fr=f.loc[dt]if dt in f.index else None
   ff=features[sid];pr=ff.loc[dt]if dt in ff.index else None
   signal=str(buys[lid]['signal_at'])[:10];sigdt=pd.Timestamp(signal)
   known=fr is not None and pr is not None and sigdt in f.index and all(pd.notna(fr[k])for k in ['close','factor','segment_id','i_target','i_floor','e0_target'])and fr.factor>0
   q=int(native['qty']);qr=eff(rules['quantity_versions'][sid],d);step=qr['sell_step'];trim=((q+2*step-1)//(2*step))*step;keep=max(0,q-trim)
   legal=0<keep<q and trim%step==0
   live_ids={x['id']for x in rec['layers']if x['sid']==sid and x['qty']}
   prior=[dict(layer=k,at=first[k]['at'],reason=first[k]['reason'])for k in live_ids if k!=lid and k in first and first_ix[k]<first_ix[lid]]
   other_hard=[dict(layer=k,at=first[k]['at'],reason=first[k]['reason'])for k in live_ids if k!=lid and k in first and first[k]['at'][:10]==d and first[k]['reason']!='CP1_add_protection']
   row=dict(window=window,day=d,layer=lid,sid=sid,name=ll[lid]['name'],industry=ll[lid]['industry'],role='mobile',
    actual_qty=q,original_actual_lifecycle_net=ll[lid]['net'],original_actual_cost=ll[lid]['cost'],
    fixed_2026H1_bought_25_layer=window=='strong'and lid in fixed_ids,
    other_live_layers_with_prior_exit_requests=prior,other_same_day_nonCP_hard_exit_requests=other_hard,
    exact_stock_ExitOrder_latch_reconstructed=False,
    known_price_hardline=known,SELL_step=step,optimistic_half_tail_qty=keep,positive_partial_retention_legal=legal,
    ACT_on=bool(rec['on']),nominal_full_quantity_risk_before_trim=None,nominal_tail_risk_after_assumed_trim=None,
    source='First actual original CP proposal; not a new retained position or counterfactual return')
   if known:
    C=D(str(fr.close));factor=D(str(fr.factor));entry=D(buys[lid]['floor']);F=D(str(native['floor']));I=D(str(fr.i_floor));H=max(entry,I)
    assert C<=F,'actual CP proposal compared wrong stored floor'
    assert float(pr.close)==float(fr.close)and pr.source_segment==fr.segment_id
    source_survives=fr.segment_id==f.loc[sigdt,'segment_id']
    hard=bool(rec['on'])and bool(fr.i_target)and bool(fr.e0_target)and source_survives and C>H
    E=bool(pr.ema_trend_known)and bool(pr.ema_trend);BB=bool(pr.bb_trend_known)and bool(pr.bb_trend)
    row.update(continuous_close=C,original_CP_checked=F,entry_hardfloor=entry,current_I=I,proposed_hardfloor=H,factor=factor,
     source_segment_survives=bool(source_survives),hard_priorities_survive=hard,EMA_license=E,BB_middle_license=BB,
     nominal_old_CP_risk=max(Z,C-F)/factor*q,nominal_full_quantity_risk_before_trim=max(Z,C-H)/factor*q,
     nominal_tail_risk_after_assumed_trim=max(Z,C-H)/factor*keep,
     tail_gross_if_trim_fills=keep*C/factor,tail_gross_pct_NAV=keep*C/factor/D(rec['nav'])*100,
     E_price_unit_upper=hard and E and legal,B_price_unit_upper=hard and BB and legal)
   else:row.update(hard_priorities_survive=None,EMA_license=None,BB_middle_license=None,E_price_unit_upper=False,B_price_unit_upper=False)
   ix=days.index(d);row['proposal_plus5_market_CLOSE']=days[ix+5]if ix+5<len(days)else None
   rows.append(row)
  del b,ds,daily
 siblings=defaultdict(list)
 for r in rows:siblings[r['window'],r['day'],r['sid']].append(r)
 for r in rows:
  a=siblings[r['window'],r['day'],r['sid']]
  r['same_sid_CP_proposal_layers']=len(a);r['same_sid_contains_hard_priority_failure']=any(x['hard_priorities_survive']is False for x in a)
 summary={}
 for w in cfg:
  strata={'all': [r for r in rows if r['window']==w]}
  for y in (['2022','2023','2024']if w=='long'else['2025','2026']):strata[y]=[r for r in strata['all']if r['day'][:4]==y]
  if w=='strong':
   strata['semiconductor_proposal_calendar_2026']=[r for r in strata['all']if r['day']>='2026-01-01'and r['industry']=='半导体']
   strata['fixed25_H1_bought_CP_only']=[r for r in strata['all']if r['fixed_2026H1_bought_25_layer']]
  else:strata['after_924']=[r for r in strata['all']if r['day']>='2024-09-24']
  for label,a in strata.items():
   z=dict(proposal_layers=len(a),stocks=len({r['sid']for r in a}),unknown=sum(not r['known_price_hardline']for r in a),
    hard_survives=sum(r['hard_priorities_survive']is True for r in a),legal_half=sum(r['positive_partial_retention_legal']for r in a),licenses={})
   for license in ['E_price_unit_upper','B_price_unit_upper']:
    u=[r for r in a if r[license]];z['licenses'][license]=dict(events=len(u),stocks=len({r['sid']for r in u}),
     retained_gross_pct_NAV_per_event=stats([r['tail_gross_pct_NAV']for r in u]),
     original_contacted_layer_net=sum((D(r['original_actual_lifecycle_net'])for r in u),Z),
     same_sid_hard_mixed=sum(r['same_sid_contains_hard_priority_failure']for r in u),
     full_risk_before_trim=stats([r['nominal_full_quantity_risk_before_trim']for r in u]))
   summary[w+'_'+label]=z
 save('CP_TAIL_ALL_ORIGINAL_NECESSARY_BOUNDS.json',rows);save('CP_TAIL_NECESSARY_BOUND_SUMMARY.json',dict(mothers=mothers,strata=summary,
  scope='Necessary price+hardline+per-layer SELL-grid upper only. No risk allocation/fees/next OPEN/actual trim/tail path or CORE handoff validated; original net is not avoidable loss or new PnL',
  capital='Event capital is not additive across dates; mixed hard/soft same-stock FIFO must be resolved before any policy',seconds=time.monotonic()-start,new_accounts=0))
 save('CP_TAIL_STATIC_SOURCE_SHA256.json',SOURCES)
 print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
