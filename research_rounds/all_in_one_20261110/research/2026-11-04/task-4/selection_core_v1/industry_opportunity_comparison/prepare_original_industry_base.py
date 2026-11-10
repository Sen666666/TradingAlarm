"""Pure aggregation of saved original records at three root-frozen closes; no model/account."""
from pathlib import Path
import pandas as pd,numpy as np,json,gzip,collections,hashlib
O=Path(__file__).resolve().parent;OLD=O.parent/'original_candidates'
DATES=['2024-09-24','2026-01-15','2022-01-24'];DSET=set(DATES)
F=pd.read_parquet(OLD/'ALL_STATIC_STOCKS_FACTS_H1_PVR.parquet');I=pd.read_csv(OLD/'INDUSTRY_H1_E0_CP_STATE_ALL90.csv');J=pd.read_csv(OLD/'ORIGINAL_PENDING_INTENTS.csv');fund=[json.loads(x) for x in (OLD/'ORIGINAL_FUNDING.jsonl').read_text().splitlines()];decs=json.loads((OLD/'ORIGINAL_SAVED_DECISION_SNAPSHOTS.json').read_text());ACT={r['at'][:10]:r['on'] for r in decs};nextday=json.loads((OLD/'FROZEN_DATES.json').read_text())['next_original_calendar_sessions']
sector=dict(zip(F.sid,F.sector_static));financial={};sha={}
for w,dates in [('long_OFF',['2022-01-24','2024-09-24']),('strong_OFF',['2026-01-15'])]:
 p=Path('new_price_trend_v1/funding/runs')/w/'pair/industry.jsonl.gz';sha[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 with gzip.open(p,'rt') as ff:events=[json.loads(x) for x in ff if x.strip()]
 events=[x for x in events if x.get('account')=='B']
 for d in dates:
  last={}
  for r in events:
   if r['day']<=d:last[r['sector']]=r
  for s,r in last.items():financial[(d,s)]=r
rows=[]
def js(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def yes(s):return s.eq(True)
for d in DATES:
 fg=F[F.date.eq(d)];ig=I[I.date.eq(d)];intents=J[J.signal_date.eq(d)]
 for ir in ig.to_dict('records'):
  s=ir['sector'];g=fg[fg.sector_static.eq(s)];j=intents[intents.sid.isin(g.sid)];fe=financial.get((d,s));ep=ir['industry_state_E0_episode']
  cl=[x for x in fund if x['at'][:10]==d and x['at'][11:16]=='15:10' and sector[x['sid']]==s]
  op=[x for x in fund if x['at'][:10]==nextday[d] and x['at'][11:16]=='09:30' and sector[x['sid']]==s];res=[x for x in op if x['result']=='reserved']
  br=collections.Counter(z for v in g.original_barriers_json for z in json.loads(v))
  r={'date':d,'sector_id_static':s,'industry_static':ir['industry_static'],'old_H1_score':ir['H1_cache_score'],'old_H1_rank0_of90':ir['cache_numeric_order_0based'],'old_H1_was_not_an_industry_topK_gate':True,'old_market_E0_valid':ir['industry_state_E0_valid'],'old_market_E0_episode':ep,'old_market_CP_receipt':ir['industry_state_receipt'],'old_market_stage':ir['industry_state_stage_name'],'old_market_stage_integer':ir['industry_state_stage'],'old_market_authorization_usable':ir['industry_state_authorization_usable'],'old_market_STATE_financial_state_owned':ir['industry_state_financial_state_owned'],'old_market_attempt_id':ir['industry_state_attempt_id'],'old_market_state_ref':ir['state_ref'],'old_actual_financial_last_event_saved':fe is not None,'old_actual_financial_last_event_day':fe['day'] if fe else None,'old_actual_financial_last_event_result':fe['result'] if fe else None,'old_actual_financial_last_event_level':fe['financial_level'] if fe else None,'old_actual_financial_last_event_episode':fe['episode'] if fe else None,'old_actual_financial_last_event_attempt':fe.get('attempt') if fe else None,'old_actual_financial_event_episode_matches_current_market':bool(fe and pd.notna(ep) and fe['episode']==ep),'old_actual_financial_current_active_status_NOT_SAVED_AS_DAILY_SNAPSHOT':True,'old_actual_level_not_same_as_active_or_available_cash':True,'old_ACT_on_at_CLOSE':ACT[d], 'old_static_pool_stocks':len(g),'old_H1_stock_known':int(g.H1_score_known.sum()),'old_PVR_stock_known':int(g.PVR_known.sum()),'old_stock_E0_asof_true':int(g.fact_e0_target.eq(1).sum()),'old_stock_I_asof_true':int(g.fact_i_target.eq(1).sum()),'old_stock_I_buy_exact_today_true':int((g.fact_exact_date_present&g.fact_i_buy.eq(True)).sum()),'old_stock_CP_receipt_today':int(g.CP_receipt.eq(True).sum()),'old_core_Q_true':int(g.original_core_Q.eq(True).sum()),'old_freshCP_mobile_Q_true':int((g.original_CP1_id.notna()&g.original_mobile_Q.eq(True)).sum()),'old_source_Q_union_stocks':int(g.source_Q_core_or_CP_mobile.sum()),'old_account_pre_size_roles_no_barriers_stocks':int(g.original_account_pre_size_roles_no_barriers.sum()),'old_actual_pending_unique_stocks':int(g.actual_native_pending.sum()),'old_actual_pending_core_intents':int(j.role.eq('core').sum()),'old_actual_pending_mobile_intents':int(j.role.eq('mobile').sum()),'old_account_held_stocks':int(g.original_held.eq(True).sum()),'old_planning_barrier_counts_json':js(dict(br)),'old_CLOSE_size_result_counts_json':js(dict(collections.Counter(x['result'] for x in cl))),'next_original_OPEN_day':nextday[d],'old_nextOPEN_funding_records':len(op),'old_nextOPEN_funding_unique_stocks':len({x['sid'] for x in op}),'old_nextOPEN_result_counts_json':js(dict(collections.Counter(x['result'] for x in op))),'old_nextOPEN_reserved_records':len(res),'old_nextOPEN_reserved_unique_stocks':len({x['sid'] for x in res}),'old_nextOPEN_reserved_pool_counts_json':js(dict(collections.Counter(x.get('pool') for x in res))),'formal_PIT_industry_opportunity_known':False}
  rows.append(r)
T=pd.DataFrame(rows);assert len(T)==270 and not T.duplicated(['date','sector_id_static']).any();assert T.old_market_STATE_financial_state_owned.eq(False).all()
T.to_csv(O/'THREE_DATES_ORIGINAL_INDUSTRY_BASE.csv',index=False);T.to_parquet(O/'THREE_DATES_ORIGINAL_INDUSTRY_BASE.parquet',index=False)
summary=[]
for d,g in T.groupby('date',sort=True):
 summary.append({'date':d,'industries':len(g),'static_stocks':int(g.old_static_pool_stocks.sum()),'old_industry_E0_true':int(g.old_market_E0_valid.eq(True).sum()),'old_market_authorization_usable':int(g.old_market_authorization_usable.eq(True).sum()),'old_market_stage_counts':g.old_market_stage.value_counts().to_dict(),'old_actual_financial_last_event_available':int(g.old_actual_financial_last_event_saved.sum()),'old_actual_financial_event_current_episode_match':int(g.old_actual_financial_event_episode_matches_current_market.sum()),'old_source_Q_stocks':int(g.old_source_Q_union_stocks.sum()),'old_pre_size_stocks':int(g.old_account_pre_size_roles_no_barriers_stocks.sum()),'old_pending_stocks':int(g.old_actual_pending_unique_stocks.sum()),'nextOPEN_reserved_unique_stocks':int(g.old_nextOPEN_reserved_unique_stocks.sum())})
(O/'ORIGINAL_PERMISSION_AND_DENOMINATORS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(O/'SOURCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
