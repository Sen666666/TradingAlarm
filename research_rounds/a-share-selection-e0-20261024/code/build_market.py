"""Explicit dated fee facts and declared A-share daily execution proxies."""
from pathlib import Path
import datetime,json,collections
import pandas as pd
from build_inputs import HERE,OLD,read,write,ref,now
from current_pool_bridge import sha256

PROXIES=['A_daily_hl_liquidity','A_same_day_sell_cash_reuse','A_historical_nonBJ_identity_from_source',
 'A_quantity_rules_research_mapping','A_availability_no_historical_ST_delisting_tag',
 'A_par1_before20150801','BSE_partial_fee_allowances','A_dividend_net80_unknown_paydate',
 'A_bonus_next_session_fraction_floor','A_source_union_calendar']

def proxy(start,end,source,**fields):
 return dict({'from':start,'to':end,'basis':'explicit_research_proxy','proxy_id':source,'source_id':source},**fields)

def build():
 out=HERE/'inputs-v1';manifest=read(out/'manifest-before-closeout.json');meta=read(out/'metadata.json')
 lines=read(out/'selection.json')['lines'];records={x['series_id']:x for x in manifest['series']}
 bse={x['code']:x for x in read(HERE/'audit/bse-listing-facts.json')['rows']}
 # Calendar observation is independent of stock selection, uses all90 indices.
 dates=set()
 for x in manifest['series']:
  if x['kind']!='sector_index':continue
  f=pd.read_parquet(x['raw']['path']);c='trade_date' if 'trade_date' in f else 'date'
  d=pd.to_datetime(f[c] if c in f else f.index)
  dates.update(str(x.date()) for x in d if '2015-01-01'<=str(x.date())<='2026-10-22')
 if any(pd.Timestamp(x).weekday()>4 for x in dates):raise ValueError('Weekend in source calendar')
 dates=sorted(dates)
 rules=dict(schema_version=1,calendar_basis='union of all90 A industry source dates; explicit research calendar proxy, not full historical suspension recovery',
  decision_cutoffs=[d+'T15:10:00+08:00' for d in dates],calendars={'A':[d+'T09:30:00+08:00' for d in dates+['2026-10-23','2026-10-26']]},
  venue_not_before={'BSE':{'from':'2021-11-15','source_id':'https://www.bse.cn/jygl_list/200010919.html'}},
  venue_versions={},quantity_versions={},availability_versions={},security_metadata=meta,fee_versions={})
 for line in lines:
  sid=line['security_id'];code=meta[sid]['code'];r=records[sid]
  venue='BSE' if sid.endswith('.BJ') else 'SSE_STAR' if code.startswith('688') else 'SSE_MAIN' if sid.endswith('.SH') else 'SZSE_CHINEXT' if code.startswith(('300','301','302')) else 'SZSE_MAIN'
  start=bse[code]['bse_start'] if venue=='BSE' else r['source_start']
  if venue=='BSE':
   rules['venue_versions'][sid]=[dict({'from':start,'to':None,'basis':'official_rule','verification_status':'verified','source_id':bse[code]['url']},venue=venue)]
  else:
   rules['venue_versions'][sid]=[proxy(start,None,'A_historical_nonBJ_identity_from_source',venue=venue)]
  q=dict(rule_id=venue+'-dated-source-mapping',buy_minimum=200 if venue=='SSE_STAR' else 100,
      buy_step=1 if venue in ('SSE_STAR','BSE') else 100,sell_step=1 if venue in ('SSE_STAR','BSE') else 100,
      allow_full_exit_odd=True,fill_step=1)
  rules['quantity_versions'][sid]=[proxy(start,None,'A_quantity_rules_research_mapping',rule=q)]
  rules['availability_versions'][sid]=[proxy(start,None,'A_availability_no_historical_ST_delisting_tag',buy_allowed=True,sell_allowed=True)]
 # Distinct legal changes retained; BSE earlier holes stay named allowances.
 boundaries=['2015-01-01','2015-08-01','2022-04-29','2023-08-18','2023-08-28','2026-10-23']
 for venue in ['SSE_MAIN','SSE_STAR','SZSE_MAIN','SZSE_CHINEXT','BSE']:
  versions=[]
  for lo,hi in zip(boundaries,boundaries[1:]):
   bj=venue=='BSE';sh=venue.startswith('SSE')
   handling=('.000125' if lo>='2023-08-28' else '.00025' if lo>='2023-08-18' else '.0005') if bj else ('.0000341' if lo>='2023-08-28' else '.0000487' if lo>='2015-08-01' else '.0000696')
   transfer='.000025' if bj else '.00001' if lo>='2022-04-29' else '.00002' if lo>='2015-08-01' else '.0003' if sh else '.0000255'
   components=[dict(name='net_brokerage',rate='.0002',minimum_local='5',basis='order'),
    dict(name='stamp_duty',rate='.0005' if lo>='2023-08-28' else '.001',side='sell',basis='fill',stress_rate=False),
    dict(name='handling',rate=handling,basis='fill'),dict(name='regulatory',rate='.00002',basis='fill'),
    dict(name='transfer',rate=transfer,basis='fill',amount_basis='par_value' if sh and lo<'2015-08-01' else 'notional')]
   # Cost2 leaves legally fixed stamp duty unchanged; doubles broker, handling,
   # regulatory, transfer allowances and slippage as a hypothetical cost stress.
   source='BSE_partial_fee_allowances' if bj else 'A_daily_hl_liquidity'
   versions.append(proxy(lo,hi,source,schedule=dict(schedule_id=venue+':'+lo,components=components),
    factual_source=ref(OLD/'audit-fees/fees.json')))
  rules['fee_versions'][venue]=versions
 write(out/'market-rules.json',rules);write(out/'fx-quotes.json',{'quotes':[],'basis':'A-only CNY identity; no FX requests'})
 protocol=dict(status='draft_before_signal_review',algorithm_changes=0,account_start='2015-01-01T00:00:00+08:00',account_end='2026-10-22T15:10:00+08:00',
  approved_proxy_ids=PROXIES,fx_max_age_days=0,participation_rate='.01',
  daily_execution={'A':dict(price_limit_policy='conservative_hl_proxy',reject_flat_day=True,slippage_bps='5',stress_slippage=True)},
  sellable_lag_sessions={'A':1},settlement_lag_sessions={'A':0},dividend_net_factor={'A':'.8'},bonus_sellable_lag_sessions={'A':1},
  fractional_split_policy='floor_position_fraction_writeoff',stale_action_mark_policy='theoretical_ex_reference',
  allow_explicit_unknown_series=True,code_sha256={p.name:sha256(p) for p in (HERE/'code').glob('*.py')},
  fee_cost2='Double named variable broker/handling/regulatory/transfer rates and slippage. Stamp duty unchanged; minima unchanged. Doubled legal components are cost allowances, not historical rates.',
  minimum_commission='per logical order across partial fills, not per order-day',
  limitations=['Current survivorship/current cap/current industry retrospective selection bias.',
    'No restored daily ST limits, suspension reasons or queue priority. Positive raw open, positive volume, H>L is a daily execution proxy.',
    'Capacity uses prior20 positive volume mean x1% and same-day total volume posthoc cap; same-day HLV does not enter selection/budget.',
    'Signal uses causal theoretical ex-price; fills raw prices. Rights not subscribed. Pay dates unknown so net80% dividend receivables are not reinvested.',
    'NonBJ historical venue from source/current code is explicit research mapping, not full PIT security master; BJ actual starts separately verified.',
    'BSE partial historical fees use explicit allowances. Pre20150801 SSE face value assumes1CNY.',
    'End positions are marked, no forced liquidation; B0 annual actual-lot equal caps may leave cash.'])
 write(out/'economic-protocol-draft.json',protocol)
 print(dict(calendar_dates=len(dates),start=dates[0],end=dates[-1],stocks=len(lines)),flush=True)

if __name__=='__main__':build()
