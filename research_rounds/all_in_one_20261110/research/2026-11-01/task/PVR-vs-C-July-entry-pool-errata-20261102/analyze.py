"""Read original July ledgers only. No runner imports or financial events."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PV=W/'pvr-slot1-native-readiness-20261101';R=PV/'runs/2025_26/pair';C=W/'g-s-C-month-continuation-20261102';READY=W/'g-s-C-AugSep-continuation-readiness-20261102';CUT='2025-07-31';Z=D(0);EPS=D('0.00000001');READS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,h=None):
 p=Path(p);s=sha(p);assert h is None or h==s,(p,'hash');assert str(p) not in READS or READS[str(p)]==s;READS[str(p)]=s;return p
def read(p,h=None):return json.loads(bind(p,h).read_text())
def gz(p,h=None,lines=False):
 with gzip.open(bind(p,h),'rt') as f:return [json.loads(s) for s in f] if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,default=str,ensure_ascii=False,indent=2)+'\n')
def eq(a,b):assert abs(a-b)<EPS,(a,b)
def parts(root,m,name):
 out=[]
 for group in ['files','extensions','month_extension']:
  ref=m.get(group,{}).get(name)
  if ref:out.append(pd.read_parquet(bind(root/ref['path'],ref['sha256'])))
 return pd.concat(out,ignore_index=True).sort_values(['sid','day']).drop_duplicates(['sid','day'],keep='last')
def total(rs):return {k:sum((D(r[k]) for r in rs),Z) for k in ['realized','unrealized','dividend','contribution','buy_gross','fees']}
def main():
 pvidx=read(PV/'FINANCIAL_ARTIFACT_SHA256.json');cidx=read(C/'july_end_analysis/ARTIFACT_SHA256.json');m=read(C/'inputs/2025_26/MANIFEST.json');meta=read(C/'inputs/2025_26/metadata.json',m['files']['metadata']['sha256']);names=read(P/'C-2022-month-native-baseline-20261102/analysis/INDUSTRY_NAMES.json')['mapping']
 raw=parts(C/'inputs/2025_26',m,'raw');raw=raw[raw.day<=CUT];rawby={s:g.set_index('day') for s,g in raw.groupby('sid')}
 book=gz(R/'B.json.gz',pvidx['runs/2025_26/pair/B.json.gz']);daily=[r for r in gz(R/'daily.jsonl.gz',pvidx['runs/2025_26/pair/daily.jsonl.gz'],True) if r['at'][:10]<=CUT];end=daily[-1];initial=daily[0];assert initial['at'][:10]=='2025-07-01' and D(initial['nav'])==1000000 and not initial['positions'] and D(initial['dividend_receivable'])==0
 trades=[t for t in book['trades'] if t['at'][:10]<=CUT];buys={t['layer']:t for t in trades if t['side']=='buy'};assert len(buys)==sum(t['side']=='buy' for t in trades)
 # First-CLOSE metadata is retained as an observation, not the entry pool.
 # Entry role/pool below comes from the fill-bound OPEN reserve.
 funding=[r for r in gz(R/'funding.jsonl.gz',pvidx['runs/2025_26/pair/funding.jsonl.gz'],True) if r['at'][:10]<=CUT]
 lm={}
 for day in daily:
  for l in day['layers']:
   if l['id'] not in lm:lm[l['id']]=dict(l,metadata_observed_at=day['at'])
 assert set(buys)<=set(lm);sold=defaultdict(list)
 for t in trades:
  if t['side']=='sell':
   for pp in t['parts']:
    fee=D(t['price'])*pp['shares']-D(pp['net_cash']);sold[pp['layer']].append(dict(pp,at=t['at'],price=t['price'],receipt=t['receipt_id'],fee_cny=fee))
 assert not [r for r in book['audit'] if r['kind'] in ['split','rights_subscription','fractional_writeoff'] and str(r.get('at',''))[:10]<=CUT],'unsupported as-of layer conversion'
 decisions={r['at']:r for r in book['decisions'] if r['at'][:10]<=CUT};divs=defaultdict(lambda:Z);divstock=defaultdict(lambda:Z);entitlements=[]
 for a in book['audit']:
  if a['kind']!='dividend_accrual' or a['receivable']['ex_at'][:10]>CUT:continue
  v=a['receivable'];sid=v['security_id'];ex=v['ex_at'];eligible={lid:b['shares']-sum(p['shares'] for p in sold[lid] if p['at']<ex) for lid,b in buys.items() if b['security_id']==sid and b['at']<ex};eligible={k:v for k,v in eligible.items() if v};den=sum(eligible.values());assert den>0 and v['paid_at'] is None,'payment or entitlement needs explicit extension'
  for lid,q in eligible.items():divs[lid]+=D(v['net_local'])*q/den
  divstock[sid]+=D(v['net_local']);entitlements.append(dict(source=v,entitled_layers=eligible))
 eq(sum(divstock.values(),Z),D(end['dividend_receivable']))
 layers={'PVR_SLOT1':[]};qstock=defaultdict(int)
 for lid,b in buys.items():
  l=lm[lid];sid=b['security_id'];sq=sum(p['shares'] for p in sold[lid]);q=b['shares']-sq;assert q>=0;qstock[sid]+=q;cost=D(b['gross_cny'])+D(b['fees_cny']);sn=sum((D(p['net_cash']) for p in sold[lid]),Z);real=sn-cost*sq/b['shares'];unreal=D(q)*D(str(rawby[sid].iloc[-1]['close']))-cost*q/b['shares'] if q else Z
  assert b['kind'] in ['core','add'];entry_role='core' if b['kind']=='core' else 'mobile'
  fr=[r for r in funding if r['result']=='reserved' and r['sid']==sid and r['at']==b['at'] and r['role']==entry_role and r['shares']>=b['shares'] and D(r['price'])==D(b['price'])];assert len(fr)==1,('ambiguous fill-bound funding reserve',lid)
  funded=[r for r in book['audit'] if r['kind']=='lot_risk_funded' and r.get('sid')==sid and r.get('at')==b['at'] and r['layer_kind']==b['kind'] and r['signal_at']==b['signal_at'] and r['shares']==fr[0]['shares'] and D(r['gross'])==D(fr[0]['price'])*fr[0]['shares']];assert len(funded)==1,('missing actual order funding proof',lid)
  reserve=[r for r in book['audit'] if r['kind']=='reserve' and r['order_id']==funded[0]['order_id']];assert len(reserve)==1 and reserve[0]['at']==b['at'] and reserve[0]['target_shares']==fr[0]['shares']
  intents=[i for i in decisions[b['signal_at']]['intents'] if i['sid']==sid and i['role']==fr[0]['role'] and i['reason']==b['reason']];assert len(intents)==1
  fees=D(b['fees_cny'])+sum((D(p['fee_cny']) for p in sold[lid]),Z)
  layers['PVR_SLOT1'].append(dict(layer=lid,sid=sid,name=meta[sid]['name'],sector=meta[sid]['sector'],industry=names[meta[sid]['sector']],signal_at=b['signal_at'],opened=b['at'],role=fr[0]['role'],pool=fr[0]['pool'],entry_reserve=fr[0],entry_order_audit=dict(funded=funded[0],reserve=reserve[0]),first_close_role=l['role'],first_close_pool=l['pool'],pool_source='fill_bound_OPEN_funding_reserve',purpose=b['reason'],canonical_receipt=intents[0].get('CP1_id'),decision_intent=intents[0],initial_qty=b['shares'],remaining_qty=q,buy_gross=D(b['gross_cny']),buy_price=b['price'],buy_raw_open=b['raw_open'],buy_receipt=b['receipt_id'],buy_fee=b['fees_cny'],actual_sell_parts=sold[lid],fees=fees,realized=real,unrealized=unreal,dividend=divs[lid],contribution=real+unreal+divs[lid],metadata_observed_at=l['metadata_observed_at']))
 assert {s:q for s,q in qstock.items() if q}==end['positions'];eq(total(layers['PVR_SLOT1'])['contribution'],D(end['nav'])-1000000);eq(total(layers['PVR_SLOT1'])['fees'],D(end['fees_cny']))
 eq(sum((D(q)*D(str(rawby[s].iloc[-1]['close'])) for s,q in end['positions'].items()),Z),D(end['inventory']))
 oldms=read(READY/'OLD_MONTHLY_SOURCES.json')['PVR_SLOT1'][0];assert oldms['NAV']==end['nav']
 for sid,v in oldms['all_stock_contribution_delta'].items():eq(sum((r['contribution'] for r in layers['PVR_SLOT1'] if r['sid']==sid),Z),D(v))
 cl=read(C/'july_end_analysis/ALL_LAYERS.json',cidx['july_end_analysis/ALL_LAYERS.json']);cr=read(C/'july_end_analysis/RESULTS.json',cidx['july_end_analysis/RESULTS.json']);navs={'PVR_SLOT1':D(end['nav'])};finals={}
 for mode in ['C10','C_BATCH20']:
  arm='2025_26-'+mode;layers[mode]=[]
  for z in cl[arm]:
   fee=D(z['buy_fee'])+sum((D(v['fee_cny']) for v in z['actual_sell_parts']),Z);layers[mode].append(dict(z,name=meta[z['sid']]['name'],industry=names[z['sector']],fees=fee,realized=D(z['realized_trade_PNL']),unrealized=D(z['unrealized_net_buy_cost']),dividend=D(z['booked_dividend_income']),contribution=D(z['total_contribution'])))
  sm=next(r for r in cr if r['arm']==arm);navs[mode]=D(sm['NAV']);eq(total(layers[mode])['contribution'],navs[mode]-1000000);eq(total(layers[mode])['fees'],D(sm['fees']))
  pp=C/'runs'/arm/'2025-07-31-CLOSE.json';finals[mode]=read(pp,cidx[str(pp.relative_to(C))]);init=finals[mode]['events'][0]['bridge'];assert D(init['nav'])==1000000 and D(init['inventory'])==0 and D(init['dividend_receivable'])==0
  eq(D(finals[mode]['account']['balance']['nav']),navs[mode])
  assert {t['execution_basis'] for t in finals[mode]['account']['trades']}=={t['execution_basis'] for t in trades}
  eq(total(layers[mode])['dividend'],D(finals[mode]['account']['balance']['dividend_receivable']))
 save('ALL_JULY_ENTRY_LAYERS.json',layers);save('PVR_DIVIDEND_ENTITLEMENTS.json',entitlements)
 stock={};industry={};bridges={};entry=[]
 for mode in layers:
  stock[mode]=[];industry[mode]=[]
  for sid in sorted({r['sid'] for r in layers[mode]}):stock[mode].append(dict(sid=sid,name=meta[sid]['name'],sector=meta[sid]['sector'],industry=names[meta[sid]['sector']],**total([r for r in layers[mode] if r['sid']==sid])))
  for sec,n in names.items():industry[mode].append(dict(sector=sec,industry=n,**total([r for r in layers[mode] if r['sector']==sec])))
 save('STOCK_CONTRIBUTIONS.json',stock);save('INDUSTRY_CONTRIBUTIONS.json',industry)
 for mode in ['C10','C_BATCH20']:
  stocks=[]
  for sid in sorted({r['sid'] for pol in ['PVR_SLOT1',mode] for r in layers[pol]}):
   A=total([r for r in layers['PVR_SLOT1'] if r['sid']==sid]);B=total([r for r in layers[mode] if r['sid']==sid]);stocks.append(dict(sid=sid,name=meta[sid]['name'],sector=meta[sid]['sector'],industry=names[meta[sid]['sector']],PVR=A,C=B,delta={k:B[k]-A[k] for k in A}))
  stocks.sort(key=lambda r:r['delta']['contribution']);inds=[]
  for sec,n in names.items():inds.append(dict(sector=sec,industry=n,delta={k:sum((r['delta'][k] for r in stocks if r['sector']==sec),Z) for k in total([])}))
  # Same signal/role/pool is descriptive pairing, not assumed equal qualification/receipt.
  def ky(r):return (r['sid'],r['signal_at'],r['role'],r['pool'])
  maps={pol:{ky(r):r for r in layers[pol]} for pol in ['PVR_SLOT1',mode]};assert all(len(maps[p])==len(layers[p]) for p in maps)
  entries=[]
  for k in sorted(maps['PVR_SLOT1'].keys()|maps[mode].keys()):
   a=maps['PVR_SLOT1'].get(k);b=maps[mode].get(k);A=total([a]) if a else total([]);B=total([b]) if b else total([]);entries.append(dict(key=k,PVR_layer=a,C_layer=b,delta={f:B[f]-A[f] for f in A},category='paired' if a and b else 'C_only_entry' if b else 'PVR_only_entry'))
  A=total(layers['PVR_SLOT1']);B=total(layers[mode]);d={k:B[k]-A[k] for k in A};eq(d['contribution'],navs[mode]-navs['PVR_SLOT1']);eq(d['realized']+d['unrealized']+d['dividend'],d['contribution']);eq(sum((r['delta']['contribution'] for r in stocks),Z),d['contribution']);eq(sum((r['delta']['contribution'] for r in entries),Z),d['contribution'])
  chain1=next(r['delta']['contribution'] for r in stocks if r['sid']=='688585.SH');chain2=next(r['delta']['contribution'] for r in stocks if r['sid']=='301511.SZ');chain3=next(r['delta']['contribution'] for r in inds if r['sector']=='URFI881268');subtotal=chain1+chain2+chain3
  bridges[mode]=dict(PVR_NAV=navs['PVR_SLOT1'],C_NAV=navs[mode],PVR=A,C=B,delta=d,alternative_gross_price_delta=d['contribution']-d['dividend']+d['fees'],alternative_fee_saving_add_once=-d['fees'],three_chains=dict(Shangwei=chain1,Defu=chain2,engineering=chain3,total=subtotal,rest=d['contribution']-subtotal,share_of_net_gap=subtotal/d['contribution']),positive_stock_deltas=sum((r['delta']['contribution'] for r in stocks if r['delta']['contribution']>0),Z),negative_stock_deltas=sum((r['delta']['contribution'] for r in stocks if r['delta']['contribution']<0),Z),full_stock_union=len(stocks),entry_keys=len(entries),entry_category_deltas={cat:sum((r['delta']['contribution'] for r in entries if r['category']==cat),Z) for cat in ['paired','C_only_entry','PVR_only_entry']})
  save(mode+'-STOCK_BRIDGE.json',stocks);save(mode+'-INDUSTRY_BRIDGE.json',inds);save(mode+'-ENTRY_BRIDGE.json',entries)
 # Current-date actual source rows/reasons for the three chains, including failures.
 opp=gz(R/'opportunities.jsonl.gz',pvidx['runs/2025_26/pair/opportunities.jsonl.gz'],True);opp=[r for r in opp if r['day']<=CUT];byday=defaultdict(set)
 for r in opp:assert r['sector']==meta[r['sid']]['sector'];byday[r['day']].add(r['sid'])
 assert len(byday)==23 and all(v==set(m['fixed_ids']) for v in byday.values())
 target={s for s,v in meta.items() if v['sector']=='URFI881268'}|{'688585.SH','301511.SZ'}
 evidence={'PVR_opportunities':[r for r in opp if r['sid'] in target],'PVR_funding':[r for r in gz(R/'funding.jsonl.gz',pvidx['runs/2025_26/pair/funding.jsonl.gz'],True) if r['at'][:10]<=CUT and r['sid'] in target], 'PVR_industry':[r for r in gz(R/'industry.jsonl.gz',pvidx['runs/2025_26/pair/industry.jsonl.gz'],True) if r['day']<=CUT and r['sector'] in ['URFI881268','URFI881265','URFI881281']], 'PVR_rank_policy':[r for r in gz(R/'rank-policy.jsonl.gz',pvidx['runs/2025_26/pair/rank-policy.jsonl.gz'],True) if r['day']<=CUT and r['sid'] in target], 'PVR_audit':[r for r in book['audit'] if str(r.get('at',''))[:10]<=CUT and r.get('sid') in target]}
 cohort=read(W/'g-s-C-engineering-causal-readonly-20261102/ALL_FRESH_CP1_COHORT.json')
 evidence['C_fresh_qualified_rows']={mode:[r for r in cohort['2025_26-'+mode] if r['sid'] in target] for mode in ['C10','C_BATCH20']}
 oldop={(r['day'],r['sid']):r for r in evidence['PVR_opportunities']};common={}
 for mode,rs in evidence['C_fresh_qualified_rows'].items():
  both=[]
  for r in rs:
   old=oldop.get((r['day'],r['sid']))
   if old and old.get('CP1_id'):
    assert old['CP1_id']==r['canonical']['receipt_id']
    both.append(dict(day=r['day'],sid=r['sid'],canonical_receipt=old['CP1_id'],old_mobile_Q=old['mobile_Q'],old_roles=old['roles'],C_stock_Q=r['stock_Q'],C_stage=r['stage_class'],C_S_new_allowed=r['S_new_allowed'],C_G_new_allowed=r['G_new_allowed']))
  common[mode]=both
 save('COMMON_CANONICAL_SIGNAL_CHECKS.json',common)
 for mode,x in finals.items():
  evidence[mode]=dict(rejections=[r for r in x['account']['rejections'] if r['sid'] in target],results=[dict(at=r['at'],Q=r['projection']['Q'],D=r['projection']['D'],trace=[z for z in r['projection']['trace'] if z['sid'] in target],industry_order=r['projection']['C_rank_binding']['industry_order']) for r in x['results'] if 'projection' in r],layers=[r for r in layers[mode] if r['sid'] in target])
 evidence['PVR_layers']=[r for r in layers['PVR_SLOT1'] if r['sid'] in target]
 evidence['upper_pre_first_fill_raw_bars']=rawby['688585.SH'].loc['2025-07-09':'2025-07-23'][['open','high','low','close']].reset_index().to_dict('records')
 save('THREE_CHAIN_TIMESTAMPS_AND_REASONS.json',evidence);save('EXACT_BRIDGES.json',bridges)
 save('POLICY_AND_INITIAL_COMPARABILITY.json',dict(initial_NAV=1000000,initial_positions=0,initial_dividend_AR=0,start='2025-07-01',end=CUT,identities=1709,sectors=90,old_opportunity_identity_days_verified=23,execution_basis_same=sorted({r['execution_basis'] for r in trades}),PVR_actual_dividends_receivable=sum(divstock.values(),Z),PVR_actual_dividends_paid=0,PVR_July_held_share_conversions=0,profits_include_fees=True,not_same_strategy='old legacy Q/stage/pools/per-fresh2%/industryrisk1% versus F1 G/S/industry H1 first/stock10 target/industryrisk5%/healthy mobile funding exit; no isolated ranking or cap causal estimate'))
 assert all(sha(p)==h for p,h in READS.items());save('READ_INPUTS.json',READS);save('CHECKS.json',dict(passed=True,account_events=0,new_strategy=0,raw_and_saved_inventory_bridge=True,old_PVR_monthly_source_bridge=True,full_stock_sector_entry_NAV_and_fee_bridge=True,initial_cash_and_identity_match=True,original_files_unchanged=True,tolerance_CNY=str(EPS)))
 print(json.dumps(bridges,default=str,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
