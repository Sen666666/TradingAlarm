import json, hashlib, pathlib, collections, math
from decimal import Decimal as D, ROUND_HALF_UP
import pandas as pd
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
P=R/'m3_ab_shared_probe_v1/tech407_admission_mask_ablation_v1'
OUT=pathlib.Path(__file__).parent
MAN=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
LIMIT=pathlib.Path('/Users/bytedance/repos/my-quant/data/processed/factors/limit_prices/limit_prices.parquet')
EPS=D('0.00000001'); CENT=D('.01')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(f,x): (OUT/f).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def notcent(x):return abs(x-x.quantize(CENT,rounding=ROUND_HALF_UP))>EPS
def audit_point(px,q,lo,hi):
 px,q,lo,hi=map(D,map(str,[px,q,lo,hi]));return {'outside_day_range':px>hi+EPS or px<lo-EPS,'single_quote_off_tick':notcent(px),'gross_not_cent_representable':notcent(px*q),'one_price_day':abs(hi-lo)<=EPS}
# Necessary conditions only; weighted-average prices may be off tick while aggregate gross is legal.
tests=[(audit_point('18.98949',300,'17.98','18.98'),{'outside_day_range':True,'single_quote_off_tick':True,'gross_not_cent_representable':True,'one_price_day':False}), (audit_point('10.005',200,9,11),{'outside_day_range':False,'single_quote_off_tick':True,'gross_not_cent_representable':False,'one_price_day':False}), (audit_point('9.995',100,10,10),{'outside_day_range':True,'single_quote_off_tick':True,'gross_not_cent_representable':False,'one_price_day':True})]
assert all(a==b for a,b in tests)
manifest={x['symbol']:x for x in json.loads(MAN.read_text())}
sources={str(MAN):sha(MAN),str(__file__):sha(__file__)}
raw={};rows=[];rounds={}
for arm in ['all1709','tech407']:
 base=P/('run_'+arm+'_once'); j=base/'EXACT_TRADE_JOURNAL.json'; a=base/'ACTIONS.json'; s=base/'SOURCE_ROUNDS.json'
 for f in [j,a,s]:sources[str(f)]=sha(f)
 actions=json.loads(a.read_text()); exact={x['action_id']:x for x in json.loads(j.read_text())}; assert len(actions)==len(exact)
 rounds[arm]={x['round_id']:x for x in json.loads(s.read_text())}
 for act in actions:
  ex=exact[act['execution_action_id']]; sid=act['sid'];day=act['day'];q=int(ex['q']);px=D(ex['exact_price']); fee=D(ex['exact_whole_order_fee'])
  assert str(ex['day'])[:10]==day and ex['side']==act['side'] and q==act['q'] and abs(px-D(str(act['price'])))<=EPS
  if sid not in raw:
   paths=[(path,h) for path,h in manifest[sid]['source_sha256'].items() if path.endswith('/signal.parquet') and '/a-share-selection-e0-' in path]
   assert len(paths)==1,(sid,paths)
   path,h=paths[0];assert sha(path)==h,(sid,path);sources[path]=h
   df=pd.read_parquet(path);assert set(df.symbol.dropna())=={sid};assert df.index.is_unique
   raw[sid]=(df,path)
  df,path=raw[sid]; rr=rounds[arm][act['round_id']]
  r={'arm':arm,'action_id':ex['action_id'],'round_id':ex['round_id'],'sid':sid,'name':rr.get('name'),'industry':rr.get('industry'),'day':day,'side':act['side'],'q':q,'exact_price':str(px),'gross':str(px*q),'fee':str(fee),'source_path':path,'historical_limit_status':'UNKNOWN_NO_DATE_MATCHED_CERTIFIED_LIMIT','fill_ack_status':'UNKNOWN_NO_EXCHANGE_OR_BROKER_RECEIPT'}
  if pd.Timestamp(day) not in df.index:r['raw_status']='UNKNOWN_MISSING_DATE';rows.append(r);continue
  b=df.loc[pd.Timestamp(day)]; vals={k:D(str(b['raw_'+k])) for k in ['open','high','low','close','volume']}
  assert all(v.is_finite() for v in vals.values())
  r.update({'raw_'+k:str(v) for k,v in vals.items()});r['raw_status']='KNOWN';r.update(audit_point(px,q,vals['low'],vals['high']))
  r['raw_price_off_tick']=any(notcent(vals[k]) for k in ['open','high','low','close'])
  r['source_kind']=str(b.source_kind);r['observed_at']=str(b.observed_at);r['quality_status']=str(b.quality_status)
  r['observed_bar']=bool(b.observed_bar);r['price_eligible']=bool(b.price_eligible);r['source_invalid']=bool(b.source_invalid);r['synthetic_event_bar']=bool(b.synthetic_event_bar)
  assert vals['low']<=vals['open']<=vals['high'] and vals['low']<=vals['close']<=vals['high']
  norm_open=vals['open'].quantize(CENT,rounding=ROUND_HALF_UP)
  intended=norm_open*(D('1.0005') if act['side'].startswith('buy') else D('.9995'))
  r['cent_open_intended_proxy']=str(intended);r['proxy_matches_open_slip']=abs(px-intended)<=EPS
  r['gross_inconsistent_after_float_cleanup']=notcent(intended*q)
  r['excess_distance_times_q']=str(max(D(0),px-vals['high'],vals['low']-px)*q)
  r['full_round_status']=rr.get('status');r['old_full_net_pnl']=rr.get('net_pnl');r['old_full_net_return']=rr.get('net_return_on_buy_cash')
  rows.append(r)
# Historical cache is evidence of absence of overlap, not inferred rule coverage.
ld=pd.read_parquet(LIMIT);sources[str(LIMIT)]=sha(LIMIT);limit_pairs=set(zip(ld.symbol,ld.trade_date.astype(str).str[:10]))
assert all(r['proxy_matches_open_slip'] for r in rows if r['raw_status']=='KNOWN')
for r in rows:r['local_limit_cache_match']=(r['sid'],r['day']) in limit_pairs

def totals(rs):
 ids=set(r['round_id'] for r in rs)
 return {'actions':len(rs),'stocks':len(set(r['sid'] for r in rs)),'rounds':len(ids),'shares':sum(r['q'] for r in rs),'gross':str(sum((D(r['gross']) for r in rs),D(0))),'fees':str(sum((D(r['fee']) for r in rs),D(0))),'actions_by_side':dict(collections.Counter(r['side'] for r in rs))}
def affected(arm,rs):
 rr=[rounds[arm][k] for k in sorted(set(r['round_id'] for r in rs))]; known=[x for x in rr if x.get('net_pnl') is not None]
 return {'rounds':len(rr),'financial_known_rounds':len(known),'old_full_net_sum':sum(x['net_pnl'] for x in known),'old_wins':sum(x['net_pnl']>0 for x in known),'old_net_return_ge30_tails':sum(x.get('net_return_on_buy_cash',-999)>=.30 for x in known),'not_corrected_strategy_return':True}
summary={'scope':'Existing sealed conditional OPEN+5bp proxy records, read-only post-close necessary-condition audit. No execution certification or counterfactual account.','synthetic_audit_tests':len(tests),'raw_symbols':len(raw),'raw_source_hashes_verified':True,'limit_cache':{'path':str(LIMIT),'rows':len(ld),'date_min':str(ld.trade_date.min()),'date_max':str(ld.trade_date.max()),'trade_matches':sum(r['local_limit_cache_match'] for r in rows)},'arms':{}}
for arm in ['all1709','tech407']:
 rs=[r for r in rows if r['arm']==arm]; z=totals(rs);z['raw_known']=sum(r['raw_status']=='KNOWN' for r in rs);z['source_quality_invalid']=sum((not r['observed_bar']) or (not r['price_eligible']) or r['source_invalid'] or r['synthetic_event_bar'] for r in rs)
 for flag in ['outside_day_range','one_price_day','single_quote_off_tick','gross_not_cent_representable','gross_inconsistent_after_float_cleanup','raw_price_off_tick']:
  selected=[r for r in rs if r.get(flag)];z[flag]=totals(selected);z[flag]['affected_old_rounds']=affected(arm,selected)
 z['outside_range_distance_not_a_pnl_correction']=str(sum((D(r['excess_distance_times_q']) for r in rs),D(0)))
 z['historical_daily_limit_unknown']=len(rs);z['queue_or_fill_unknown']=len(rs);summary['arms'][arm]=z
# Verify all sources again after read-only audit.
assert all(sha(p)==h for p,h in sources.items())
dump('AUDIT_SUMMARY.json',summary);dump('TRADE_AUDIT.json',rows);pd.DataFrame(rows).to_csv(OUT/'TRADE_AUDIT.csv',index=False);dump('OUTSIDE_DAY_RANGE.json',[r for r in rows if r.get('outside_day_range')]);dump('SOURCE_HASHES.json',sources);dump('TEST_RESULTS.json',{'audit_tests':tests,'passed':True})
dump('OUTPUT_HASHES.json',{f.name:sha(f) for f in OUT.iterdir() if f.is_file() and f.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,ensure_ascii=False,indent=2));print('OUTSIDE_CASES',json.dumps([{k:r[k] for k in ['arm','sid','name','day','side','q','exact_price','raw_open','raw_high','raw_low','one_price_day','old_full_net_pnl']} for r in rows if r.get('outside_day_range')],ensure_ascii=False))
