"""Static saved-input/JSON competition diagnostic; never construct/restore accounts."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,date
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
from dataclasses import dataclass
from typing import Mapping
import ast,json,hashlib,math,sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

O=Path(__file__).resolve().parent
B=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
N=W/'g-s-historical-native-nextsession-20261101'
U=W/'universe-cp1-inputs-20261031'
V=W/'pvr-slot1-native-readiness-20261101'
RANK=V/'native_rank.py'
RULE=RR/'rs-h1-execution-20261025/code/market_rules.py'
LEDGER=RULE.with_name('sector_account.py')
SOURCES={};EXPECTED_MISMATCH=[];Z=D(0)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p);value=sha(p);SOURCES[str(p)]=value
 if expected and value!=expected:raise ValueError('frozen source differs '+str(p))
 return p
def read(p):return json.loads(bind(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(date,datetime,pd.Timestamp,D,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,value):(O/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def finite(x):return x is not None and bool(pd.notna(x)) and math.isfinite(float(x))
def extract(path,names,ns):
 tree=ast.parse(bind(path).read_text());body=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
 assert {n.name for n in body}==set(names)
 exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path)+'::pure_static_subset','exec'),ns)
 return ns

def pure_sources():
 ns={'math':math};extract(RANK,['priority_plan'],ns)
 mr={'date':date,'datetime':datetime,'Mapping':Mapping};extract(RULE,['RuleUnavailable','day','version_on','market_identity_on'],mr)
 fs={'dataclass':dataclass,'Decimal':D,'ZERO':Z,'Mapping':Mapping,'ROUND_CEILING':ROUND_CEILING,'ROUND_HALF_UP':ROUND_HALF_UP,'__name__':__name__}
 extract(LEDGER,['dec','positive','FeeComponent','FeeSchedule'],fs)
 return ns['priority_plan'],mr,fs

PRIORITY,MR,FS=pure_sources()

def ranks(ids,h1):
 return {s:n for n,s in enumerate(sorted(ids,key=lambda s:(-round(float(h1[s]),12) if finite(h1.get(s)) else 1,s)))}

def priority(domain,hr,pv):
 _,log=PRIORITY([dict(sid=s,rank=hr[s],role='mobile') for s in domain],lambda s,d:pv.get(s),'fixed-close')
 return sorted(log,key=lambda r:r['priority_rank'])

def dated(sid,on,rules,protocol):
 try:
  v=MR['market_identity_on'](rules,sid,on,protocol['approved_proxy_ids'])
  av=MR['version_on'](rules['availability_versions'].get(sid,[]),on,protocol['approved_proxy_ids'])
  q=MR['version_on'](rules['quantity_versions'].get(sid,[]),on,protocol['approved_proxy_ids'])['rule']
  f=MR['version_on'](rules['fee_versions'].get(v['venue'],[]),on,protocol['approved_proxy_ids'])['schedule']
  schedule=FS['FeeSchedule'](f['schedule_id'],tuple(FS['FeeComponent'](**c) for c in f['components']))
  return dict(known=True,buy_allowed=av['buy_allowed'],sell_allowed=av['sell_allowed'],quantity=q,schedule=schedule)
 except MR['RuleUnavailable'] as e:return dict(known=False,reason=str(e))

def fee(q,p,schedule,sid,rules):
 return sum(schedule.incremental('buy',D(q)*p,{}, {},1,shares=q,par_value=rules['security_metadata'].get(sid,{}).get('par_value')).values(),Z)

def nextday(day,rules):return next(t[:10] for t in rules['calendars']['A'] if t[:10]>day)

def context_cap(sec,scopes,new=False):
 s=scopes[sec];g=scopes['G'];choices=[]
 if s['support'] and s['mature'] and (s['permit'] or not new):choices.append(('S',D('.8')))
 if g['support'] and (g['permit'] or not new):choices.append(('G',D('.2')))
 if not new and s['support']:choices.append(('T',D('.02')))
 return max(choices,key=lambda x:x[1]) if choices else (None,Z)

def raw_capacity(sid,day,meta):
 r=meta[sid]['runtime_record'];p=bind(r['raw']['path'],r['raw']['sha256'])
 f=pq.read_table(p,filters=[('trade_date','<=',pd.Timestamp(day).to_pydatetime())],columns=['trade_date','volume','price_eligible','observed_bar','synthetic_event_bar']).to_pandas()
 valid=f.price_eligible&f.observed_bar&~f.synthetic_event_bar&f.volume.gt(0)
 last=f.loc[valid].tail(20)
 return int(last.volume.mean()*.01) if len(last)==20 else None

def resource_rows(a):
 assert not a['buys'],'pending real orders need additional resource treatment'
 rows=[]
 for z in a['layers']:
  if not z['qty']:continue
  sid=z['sid'];mark=D(a['market_marks'][sid]);factor=D(a['market_factors'][sid]);floor=D(a['facts_floors'][sid] if z['kind']=='core' else z['floor'])/factor
  locks=[x for x in a['policy']['locks'].values() if x['lot']==z['id'] and x['remaining']]
  qty=sum(x['remaining'] for x in locks);risk=D(z['qty']-qty)*max(Z,mark-floor)
  for e in locks:
   assert all(e.get(k) is not None for k in ['q0','e0','ratio','h'])
   risk+=max(D(e['remaining'])*max(Z,mark-floor),D(e['e0'])*D(e['remaining'])/(D(e['ratio'])*D(e['q0'])))
  meta=a['capital_meta'][str(z['id'])]
  rows.append(dict(sid=sid,layer=z['id'],sector=meta['sector'],kind=z['kind'],role=meta['role'],pool=meta['pool'],
    purpose=meta['purpose'],qty=z['qty'],capital=D(z['qty'])*mark,risk=risk,raw_mark=mark,raw_floor=floor,
    locked_qty=qty,lock_reasons=[e['reason'] for e in locks],opened=z['opened']))
 assert sum((r['capital'] for r in rows),Z)==D(a['balance']['resources']['capital'])
 assert sum((r['risk'] for r in rows),Z)==D(a['balance']['resources']['risk'])
 return rows

def minimum_check(c,rows,a,rules,used=None):
 used=used or []
 if not c['minimum_input_known']:return dict(fit=None,reasons=['UNKNOWN_minimum_inputs'])
 nd=D(a['policy']['nd']);nav=D(a['balance']['nav']);q=c['minimum_quantity'];p=c['close_buy_proxy'];gross=D(q)*p
 f=c['minimum_fee'];newrisk=D(q)*max(Z,p-c['fresh_raw_floor']);totalfees=sum((x['fee'] for x in used),Z)+f;bn=nav-totalfees
 cap=sum((x['capital'] for x in rows),Z)+sum((x['gross'] for x in used),Z)
 risk=sum((x['risk'] for x in rows),Z)+sum((x['risk'] for x in used),Z)
 sc=sum((x['capital'] for x in rows if x['sector']==c['sector']),Z)+sum((x['gross'] for x in used if x['sector']==c['sector']),Z)
 sr=sum((x['risk'] for x in rows if x['sector']==c['sector']),Z)+sum((x['risk'] for x in used if x['sector']==c['sector']),Z)
 stock=sum((x['capital'] for x in rows if x['sid']==c['sid']),Z)+sum((x['gross'] for x in used if x['sid']==c['sid']),Z)
 reasons=[]
 if gross+f+sum((x['gross']+x['fee'] for x in used),Z)>D(a['balance']['available'])-nd*D('.1'):reasons.append('cash_reserve10')
 if cap+gross>bn*D('.9'):reasons.append('account_capital90')
 if sc+gross>nd*c['sector_cap_fraction']:reasons.append('industry_cap')
 if stock+gross>nd*D('.1'):reasons.append('stock10')
 if sr+newrisk>bn*D('.05'):reasons.append('sector_risk5')
 if risk+newrisk>bn*D('.06'):reasons.append('account_risk6')
 if c['prior20_capacity_upper'] is None:reasons.append('UNKNOWN_prior20_capacity')
 elif q>c['prior20_capacity_upper']:reasons.append('prior20_capacity_upper')
 if p<=c['fresh_raw_floor']:reasons.append('at_or_below_protection')
 return dict(fit=not reasons,reasons=reasons,gross=gross,fee=f,risk=newrisk,quantity=q)

def candidate(sid,st,sector,scopes,day,rules,protocol,meta):
 use,cap=context_cap(sector,scopes,True);av=dated(sid,nextday(day,rules),rules,protocol)
 known=bool(av['known'] and av['buy_allowed'] is True and finite(st['close']) and st['i_floor'] is not None and st['cp_floor'] is not None)
 r=dict(sid=sid,sector=sector,fresh_use=use,sector_cap_fraction=cap,minimum_input_known=known,
   fresh_receipt_id=st['receipt']['event_id'],original_stock_Q=True,scope_permit=bool(use),
   current_I_valid=st['i_valid'],actual_next_open_execution='UNKNOWN; CLOSE-price proxy only')
 if known:
  factor=D(str(meta[sid]['current_factor']));p=D(str(st['close']))*D('1.0005');q=av['quantity']['buy_minimum']
  r.update(minimum_quantity=q,close_buy_proxy=p,fresh_raw_floor=max(D(str(st['i_floor'])),D(str(st['cp_floor'])))/factor,
    minimum_fee=fee(q,p,av['schedule'],sid,rules),minimum_notional=D(q)*p,
    prior20_capacity_upper=raw_capacity(sid,day,meta))
 return r

def account_case(key,day):
 close=N/'run'/key/'close'/f'{day}-CLOSE.json';cl=read(close);a=cl['account'];stocks=cl['last_stock_state'];mapping={x['sid']:x for x in cl['mapping'][-1]['stocks']}
 assert len(stocks)==len(mapping)==1709
 meta=read(N/'inputs'/key/'metadata.json');sel=read(N/'inputs'/key/'selection.json');rules=read(N/'inputs'/key/'rules.json');protocol=read(N/'inputs'/key/'protocol.json')
 facts=pd.read_parquet(bind(N/'inputs'/key/'extensions/facts.parquet')).set_index('sid');pvdf=pd.read_parquet(bind(N/'inputs'/key/'extensions/pvr.parquet'));hdf=pd.read_parquet(bind(N/'inputs'/key/'extensions/h1.parquet'))
 pv=pvdf.set_index('sid').score.to_dict();h1=hdf.set_index('sid').score.to_dict();ids=list(stocks);hr=ranks(ids,h1)
 for sid in ids:meta[sid]['current_factor']=stocks[sid]['close'] and (a['market_factors'].get(sid) or (float(facts.loc[sid,'factor']) if sid in facts.index else None))
 actual_priority=cl['mapping'][-1]['priority'];original_domain=[x['sid'] for x in actual_priority]
 recomputed=priority(original_domain,hr,pv);by={x['sid']:x for x in recomputed}
 for old in actual_priority:
  for f in ['original_H1_rank','priority_rank','original_slot','final_slot','PVR','PVR_ready']:assert clean(old[f])==clean(by[old['sid']][f]),(key,old['sid'],f)
 rows=resource_rows(a);scopes=a['policy']['scopes'];core=[x for x in rows if x['kind']=='core'];mobile=[x for x in rows if x['kind']!='core']
 assert a['policy']['act']['on'] and a['policy']['incident'] is None,'ACT shared constraint needs explicit additional handling'
 holdings=[]
 for r in mobile:
  sid=r['sid'];s=stocks[sid];use,cap=context_cap(r['sector'],scopes,False)
  independent=[x for x in r['lock_reasons'] if x!='actionable_S_funding']
  legal=bool(s['i_valid'] is True and r['raw_mark']>r['raw_floor'] and use and not independent)
  holdings.append(dict(r,intrinsic_retention_legal=legal,retention_support=use,retention_sector_ceiling=cap,
   original_stock_Q=mapping[sid]['stock_Q'],new_intent_q=s['q'],fresh_CP1=bool(s['receipt']),
   no_fresh_required_to_retain=True,A_only_funding_qty=r['locked_qty'] if r['lock_reasons'] and not independent else 0))
 holdids={r['sid'] for r in holdings if r['intrinsic_retention_legal']}
 fresh={};blocked=[]
 for sid,s in stocks.items():
  if not s['receipt'] or not s['q'] or not s['i_valid']:continue
  sec=meta[sid]['sector'];use,cap=context_cap(sec,scopes,True)
  if not use:blocked.append(dict(sid=sid,reason='no_G_or_mature_S_new_risk_permission'));continue
  c=candidate(sid,s,sec,scopes,day,rules,protocol,meta)
  c['recorded_responsibility_blocked']=sid in a['exits'] or any(x['sid']==sid and x['remaining'] for x in a['policy']['locks'].values())
  c['independent_responsibility_blocked']=any(x['sid']==sid and x['remaining'] and x['reason']!='actionable_S_funding' for x in a['policy']['locks'].values())
  if c['independent_responsibility_blocked']:blocked.append(dict(sid=sid,reason='independent_exit_responsibility'));continue
  c['standalone_minimum']=minimum_check(c,rows,a,rules)
  c['as_recorded_executable_minimum']=bool(c['standalone_minimum']['fit'] and not c['recorded_responsibility_blocked'])
  fresh[sid]=c
 union=holdids|set(fresh);order=priority(union,hr,pv);position={r['sid']:n+1 for n,r in enumerate(order)}
 name={s:meta[s]['name'] for s in ids};combined=[];used=[]
 for p in order:
  sid=p['sid'];held=[x for x in holdings if x['sid']==sid and x['intrinsic_retention_legal']]
  x=dict(p,competition_rank=position[sid],name=name[sid],sector=meta[sid]['sector'],
    existing_mobile=bool(held),fresh_mobile=sid in fresh,current_mobile_capital=sum((r['capital'] for r in held),Z),
    retain_only_without_fresh=bool(held and sid not in fresh),candidate=fresh.get(sid))
  if sid in fresh:
   check=minimum_check(fresh[sid],rows,a,rules,used)
   check['real_responsibility_blocked']=fresh[sid]['recorded_responsibility_blocked']
   x['rank_order_minimum_pack']=check
   if check['fit'] and not check['real_responsibility_blocked']:used.append(dict(sid=sid,sector=x['sector'],gross=check['gross'],fee=check['fee'],risk=check['risk']))
  combined.append(x)
 reductions=cl['lifecycle'][-1]['allocation']['reductions'];demand=cl['lifecycle'][-1]['allocation']['demand']
 reduced_ids={r['sid'] for r in reductions};demand_ids={r['sid'] for r in demand};pairs=[]
 for old in sorted(holdids):
  for new in sorted(set(fresh)-{old}):
   pairs.append(dict(old=old,old_name=name[old],new=new,new_name=name[new],old_rank=position[old],new_rank=position[new],
    new_outranks_old=position[new]<position[old],new_already_held=new in holdids,old_PVR=pv.get(old),new_PVR=pv.get(new),
    old_A_funding_requested=old in reduced_ids,new_A_demand=new in demand_ids,
    new_standalone_minimum_fit=fresh[new]['standalone_minimum']['fit'],
    not_an_actual_swap=True))
 sectors=[];nd=D(a['policy']['nd']);coretotal=sum((r['capital'] for r in core),Z)
 for sec in sorted(scopes.keys()-{'G'}):
  eligible=[x for x in combined if x['sector']==sec];sec_core=sum((r['capital'] for r in core if r['sector']==sec),Z)
  supply=Z
  for x in eligible:
   other_core=sum((r['capital'] for r in core if r['sid']==x['sid']),Z)
   supply+=max(Z,nd*D('.1')-other_core) if x['fresh_mobile'] else x['current_mobile_capital']
  use,cap=context_cap(sec,scopes,True)
  if not use:use,cap=context_cap(sec,scopes,False)
  ceiling=max(Z,min(nd*cap-sec_core,nd*D('.9')-coretotal,supply))
  sectors.append(dict(sector=sec,existing_mobile_names=sum(x['existing_mobile'] for x in eligible),fresh_names=sum(x['fresh_mobile'] for x in eligible),
   permitted_scope_ceiling=cap,core_capital=sec_core,nominal_mobile_supply_upper_bound=ceiling,
   upper_bound_is_not_joint_feasible_target=True,risk_cash_actual_sale_constraints_still_apply=True))
 save(key+'-COMPETITION.json',combined);save(key+'-HOLDINGS.json',dict(all_resources=rows,core_restricted=core,mobile_intrinsic=holdings));save(key+'-REPLACEMENT_PAIRS.json',pairs);save(key+'-SECTOR_UPPER_BOUNDS.json',sectors)
 return dict(key=key,day=day,ids=ids,h1=h1,pv=pv,meta=meta,combined=combined,pairs=pairs,holdings=holdings,
  summary=dict(stock_identities=1709,exact_facts=len(facts),PVR_explicit=len(pv),PVR_NA=sum(not finite(x) for x in pv.values()),
   H1_ready=sum(finite(h1.get(s)) for s in ids),positive_layers=len(rows),positive_stock_denominator=len(a['balance']['quantities']),
   core_layers=len(core),core_capital=coretotal,core_risk=sum((r['risk'] for r in core),Z),
   mobile_layers=len(mobile),legal_mobile_retention_names=len(holdids),fresh_CP1_original=sum(bool(s['receipt']) for s in stocks.values()),
   fresh_mobile_permission_names=len(fresh),union_names=len(union),union_PVR_NA=sum(not finite(pv.get(s)) for s in union),
   standalone_minimum_fits=sum(bool(x['standalone_minimum']['fit']) for x in fresh.values()),
   as_recorded_minimum_fits=sum(x['as_recorded_executable_minimum'] for x in fresh.values()),
   rank_order_joint_minimum_unit_witness_count=len(used),rank_order_minimum_unit_witness=used,
   A_K=len(a['policy']['k']),A_equal_fraction=D('.8')/len(a['policy']['k']),A_demands=demand,A_reductions=reductions,
   A_pair_count=sum(p['old_A_funding_requested'] and p['new_A_demand'] for p in pairs),
   A_new_lower_than_old_pairs=sum(p['old_A_funding_requested'] and p['new_A_demand'] and not p['new_outranks_old'] for p in pairs),
   A_new_higher_than_old_pairs=sum(p['old_A_funding_requested'] and p['new_A_demand'] and p['new_outranks_old'] for p in pairs),
   balance=a['balance'],ACT=a['policy']['act'],incident=a['policy']['incident'],blocked_fresh=blocked,
   original_new_intent_priority_exact=True,joint_target_solver_status='NOT_READY; ranking and conditional minimum-unit capacity only'))

def sector_states(day):
 cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json');out={}
 specs=[('G',B/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet')]+[(n['sector'],Path(n['daily_result_path'])) for n in cat if n['domain']=='NATIVE1709']
 for sec,p in specs:
  f=pq.read_table(bind(p),filters=[('day','<=',day)]).to_pandas();assert day in f.index
  context=None;advance=False
  for ev in f.events:
   for e in ev:
    if e.startswith('price_failure') or e=='source_changed_context_ended':context=None;advance=False
    elif e in ['break_started','repair_restored']:context=e;advance=False
    elif e=='price_advance' and context:advance=True
  r=f.loc[day];support=r['mode']=='ACTIVE' and r['pending_failure_at'] is None
  out[sec]=dict(support=support,permit=bool(r.permit_next_open),mature=bool(support and advance),mode=r['mode'],breadth=r.breadth)
 return out

def extra_cases():
 days=['2026-04-30','2026-05-07'];sm=read(U/'STOCK_MANIFEST.json');vm=read(V/'SCORES_MANIFEST.json');vs={x['symbol']:x for x in vm['entries']}
 ids=[x['symbol'] for x in sm];base=read(N/'inputs/2025_26/metadata.json');rules=read(N/'inputs/2025_26/rules.json');protocol=read(N/'inputs/2025_26/protocol.json');selection=read(N/'inputs/2025_26/selection.json');lines={x['security_id']:x for x in selection['lines']}
 hp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');z=np.load(bind(hp),allow_pickle=False);ix={s:i for i,s in enumerate(z['symbols'])};dates=pd.DatetimeIndex(z['dates'])
 scores=z['score']  # NPZ unpacks on every __getitem__; cache the immutable matrix once.
 scopes={d:sector_states(d) for d in days};observations={d:[] for d in days};pvs={d:{} for d in days};hs={d:{s:float(scores[dates.get_loc(pd.Timestamp(d)),ix[s]]) for s in ids} for d in days}
 for n,x in enumerate(sm):
  sid=x['symbol'];refs=x['refs'];expected=x['output_sha256']
  f=pd.read_parquet(bind(refs['facts'],expected[refs['facts']]));cp=pd.read_parquet(bind(refs['CP1'],expected[refs['CP1']]));receipts=read(bind(refs['receipts'],expected[refs['receipts']]))
  pv=pd.read_parquet(bind(V/'scores'/f'{sid}.parquet',vs[sid]['output_sha256']))
  sec=base[sid]['sector'];line=lines[sid]
  for day in days:
   t=pd.Timestamp(day);pvs[day][sid]=pv.loc[t,'score'];q=f.loc[t] if t in f.index else None
   can=[r for r in receipts if r['confirmed_day']==day];assert len(can)<=1
   av=dated(sid,day,rules,protocol)
   if not can:observations[day].append(dict(sid=sid,canonical=False,facts_exact=q is not None));continue
   r=can[0];assert not r['trace_unknown'] and t in cp.index and cp.loc[t,'receipt'] and cp.loc[t,'candidate']==r['original_candidate']
   valid=bool(q is not None and q.e0_ready and q.i_target and finite(q.i_floor) and finite(hs[day][sid]) and line['current_stock'] and line['company_cap_cny']>1e10 and av['known'] and av['buy_allowed'] is True)
   if not valid:observations[day].append(dict(sid=sid,canonical=True,stock_Q=False,facts_exact=q is not None));continue
   use,cap=context_cap(sec,scopes[day],True)
   if not use:observations[day].append(dict(sid=sid,canonical=True,stock_Q=True,no_expansion_permission=True,facts_exact=True));continue
   meta={sid:dict(base[sid],current_factor=q.factor)}
   st=dict(close=q.raw_close,i_floor=q.i_floor,cp_floor=r['original_candidate'],i_valid=True,receipt={'event_id':r['receipt_id']})
   c=candidate(sid,st,sec,scopes[day],day,rules,protocol,meta)
   observations[day].append(dict(c,name=base[sid]['name'],canonical=True,stock_Q=True,facts_exact=True))
  if (n+1)%500==0:print('CACHED_2026_INPUTS_READ',n+1,flush=True)
 result={}
 for day in days:
  fresh=[x for x in observations[day] if x.get('fresh_use')];hr=ranks(ids,hs[day]);order=priority([x['sid'] for x in fresh],hr,pvs[day]);by={x['sid']:x for x in fresh};ranked=[dict(x,competition_rank=i+1,details=by[x['sid']]) for i,x in enumerate(order)]
  save(day+'-ALL1709_DISPOSITIONS.json',observations[day]);save(day+'-ALL_SECTOR_FRESH_COMPETITION.json',ranked)
  sector={}
  for sec in sorted(scopes[day].keys()-{'G'}):
   group=[x for x in ranked if x['details']['sector']==sec]
   sector[sec]=dict(fresh_names=len(group),ranks=[x['competition_rank'] for x in group],first20_count=sum(x['competition_rank']<=20 for x in group),market=scopes[day][sec],
    minimum_units_known=sum(x['details']['minimum_input_known'] for x in group),nominal_stock10_supply_upper_fraction=min(D('.8') if scopes[day][sec]['mature'] else D('.2'),D('.1')*len(group)))
  save(day+'-SECTOR_OPPORTUNITY.json',sector)
  result[day]=dict(stock_denominator=len(ids),stock_dispositions=len(observations[day]),facts_exact=sum(x['facts_exact'] for x in observations[day]),
    canonical_receipts=sum(x['canonical'] for x in observations[day]),fresh_mobile_permission_names=len(fresh),PVR_explicit=len(pvs[day]),PVR_NA=sum(not finite(x) for x in pvs[day].values()),
    top20=[dict(sid=x['sid'],name=x['details']['name'],sector=x['details']['sector'],PVR=x['PVR'],rank=x['competition_rank']) for x in ranked[:20]],
    strict_semiconductor=sector['URFI881121'],electronic_chemicals=sector['URFI881172'],all_sectors_kept=90,
    actual_GS_account_inventory='NOT_AVAILABLE; no empty account or prior SC/PVR state substituted',joint_account_feasible_targets='UNKNOWN')
 return result

def posthoc(cases):
 sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};cache={};results={}
 for k,case in cases.items():
  day=case['day'];names={x['sid'] for x in case['combined']};price={}
  for sid in names:
   if sid not in cache:cache[sid]=pd.read_parquet(bind(sm[sid]['refs']['facts'],sm[sid]['output_sha256'][sm[sid]['refs']['facts']]),columns=['close'])
   f=cache[sid];t=pd.Timestamp(day);i=f.index.get_loc(t) if t in f.index else None
   def change(n):return float(f.close.iloc[i+n]/f.close.iloc[i]-1) if i is not None and 0<=i+n<len(f) else None
   price[sid]=dict(prior1=change(-1),prior5=change(-5),prior21=change(-21),forward5=change(5),forward21=change(21))
   # Prior change must run from old price to current, not inverse return.
   for j in [1,5,21]:
    if i is not None and i>=j:price[sid]['prior'+str(j)]=float(f.close.iloc[i]/f.close.iloc[i-j]-1)
  pairs=[]
  for p in case['pairs']:
   if not p['new_outranks_old']:continue
   old=price[p['old']];new=price[p['new']]
   pairs.append(dict(p,old_price_path=old,new_price_path=new,
    old_beats_new_forward5=None if old['forward5'] is None or new['forward5'] is None else old['forward5']>new['forward5'],
    old_beats_new_forward21=None if old['forward21'] is None or new['forward21'] is None else old['forward21']>new['forward21'],
    consolidation_vs_one_day_hot_descriptive=bool(old['prior21'] is not None and old['prior21']>0 and old['prior5']<0 and new['prior1']>0)))
  save(k+'-POSTHOC_ALL_PRICE_PATHS.json',price);save(k+'-POSTHOC_HIGHER_NEWCOMER_PAIRS.json',pairs)
  results[k]=dict(pair_count=len(pairs),old_outperforms_at5=sum(x['old_beats_new_forward5'] is True for x in pairs),old_outperforms_at21=sum(x['old_beats_new_forward21'] is True for x in pairs),
    consolidation_hot_counterexamples=[x for x in pairs if x['consolidation_vs_one_day_hot_descriptive'] and (x['old_beats_new_forward5'] or x['old_beats_new_forward21'])],
    price_opportunity_not_account_return=True)
 return results

def main():
 assert not (O/'SUMMARY.json').exists(),'do not overwrite completed diagnostic'
 save('FREEZE.json',dict(scope='read-only two-principle static competition',protocol_sha256=sha(O/'PROTOCOL.txt'),analysis_sha256=sha(__file__),dates=['2022-01-06','2025-07-03','2026-04-30','2026-05-07'],full_joint_target_solver=False))
 oldindex=sha(N/'INPUT_OUTPUT_SHA256.json');cases={k:account_case(k,d) for k,d in [('2022','2022-01-06'),('2025_26','2025-07-03')]}
 ranks_before={p.name:sha(p) for p in O.glob('*COMPETITION.json')}
 extras=extra_cases();ranks_before.update({p.name:sha(p) for p in O.glob('*COMPETITION.json')})
 # Explicit NA/tie regression against the original frozen pure function.
 log=priority(['a','b','c'],{'a':10,'b':77,'c':108},{'a':5.,'b':None,'c':8.});assert [r['sid'] for r in log]==['c','b','a'] and log[1]['priority_rank']==77
 tie=priority(['a','b'],{'a':10,'b':77},{'a':1.0000000000001,'b':1.0000000000002});assert [r['sid'] for r in tie]==['a','b']
 save('RANKING_BEFORE_FUTURE_EVALUATION_SHA256.json',ranks_before)
 future=posthoc(cases)
 assert ranks_before=={p:sha(O/p) for p in ranks_before}
 assert oldindex==sha(N/'INPUT_OUTPUT_SHA256.json')
 assert SOURCES=={p:sha(p) for p in SOURCES}
 save('SOURCE_SHA256.json',SOURCES)
 save('SUMMARY.json',dict(account_cases={k:x['summary'] for k,x in cases.items()},extra_2026=extras,posthoc=future,
  old_artifact_index_unchanged=True,sources_unchanged=True,all_real_new_intent_priority_exact=True,NA_slot_and_12decimal_tie_tests=True,
  future_evaluation_did_not_change_ranks=True,financial_accounts=0,account_restores=0,financial_events=0,orders_generated=0,indicator_recalculations=0,downloads=0))
 print('STATIC_DIAGNOSTIC_COMPLETE',json.dumps(clean({k:x['summary'] for k,x in cases.items()}),ensure_ascii=False)[:1600],flush=True)

if __name__=='__main__':main()
