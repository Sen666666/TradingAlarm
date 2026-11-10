"""Curated primary-source fee table; offline, no account run."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

OUT = Path(__file__).resolve().parent
END = '2026-10-23'
SOURCES = {
 'bj2023handling': dict(url='https://www.sse.com.cn/home/component/news/c/c_20230818_5725376.shtml', title='SSE转载证监会：沪深北交易所降低交易经手费', published='2023-08-18', evidence='root agent verified official page/big5 mirror: BJ0.025% to0.0125% effective2023-08-28; preceding50% cut in2022-12, exact day not verified'),
 'a2015': dict(url='https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988866.shtml', title='沪深交易所、中国结算降低A股交易结算收费答问', published='2015-07-01', evidence='direct official page read; URL migration date is not publication date'),
 'a2022transfer': dict(url='https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2022/CT03722B.pdf', title='CT/037/22: A-share transfer fee revision', published='2022-04-28', evidence='direct official circular read; explicitly states SSE/SZSE A-share fees, also applies Northbound'),
 'a2023handling': dict(url='https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230818_5725378.shtml', title='上交所下调股票交易经手费30%', published='2023-08-18', evidence='direct official page read'),
 'a2023stamp': dict(url='https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230827_5725662.shtml', title='证券交易印花税实施减半征收', published='2023-08-27', evidence='root agent verified official page; this subagent direct fetch timed out twice'),
 'a2022stampbase': dict(url='https://www.sse.com.cn/services/investors/questions/pay/c/c_20220421_5701222.shtml', title='SSE investor fee FAQ', published='2022-04-21', evidence='root agent verified official page: seller-only 0.1% stamp duty'),
 'a2012reg': dict(url='https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988604.shtml', title='调整证券交易监管费收费标准', published='2012-08-31', evidence='direct official page read; retrospective effective date2012-01-01, settlement parameter date2012-09-01'),
 'sz2019fees': dict(url='https://investor.szse.cn/warning/activities/stockintroduction/t20190531_567540.html', title='深交所股市入门300问第十篇', published='2019-05-31', evidence='official indexed text read; direct fetch twice timed out; explicit 0.02 per mille regulatory fee and seller-only 1 per mille stamp duty'),
 'hk2021stamp': dict(url='https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2021/ce_SEHK_CT_080_2021.pdf', title='CT/080/21 Increase of Stamp Duty', published='2021-06-03', evidence='direct official circular read'),
 'hk2023stamp': dict(url='https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2023/ce_SEHK_CT_158_2023.pdf', title='CT/158/23 Reduction of Stamp Duty', published='2023-11-15', evidence='direct official circular read'),
 'hk2023trade': dict(url='https://www.hkex.com.hk/News/Market-Communications/2022/221101news?sc_lang=en', title='HKEX cash market trading fee change', published='2022-11-01', evidence='direct official page read'),
 'hkcurrent': dict(url='https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-%28Hong-Kong%29/Trading/Transaction?sc_lang=en', title='HKEX Transaction fee schedule', published=None, evidence='direct current official page read, historical levy effective dates explicitly included'),
 'southboundtax': dict(url='https://www.sse.com.cn/services/hkexsc/tax/', title='SSE 港股通交易税费', published=None, evidence='direct current official page read; confirms Southbound tax applicability, SFC/AFRC dates and rounding'),
 'hk2025settlement': dict(url='https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/HKSCC/2025/HKSCC-Circular_Stock-Settlement-Fee-Restructure_20250220_f_clean.pdf', title='PT/OES/HKSCC/008/2025 stock settlement fee', published='2025-02-21', evidence='direct official circular read; old/new rates and boundaries, initially June subject to readiness'),
 'hk2025effective': dict(url='https://www.hkex.com.hk/News/News-Release/2025/250820news?sc_lang=en', title='HKEX 2025 interim results and attachment page11', published='2025-08-20', evidence='root agent verified official release: new fee applied to Exchange Trades executed from2025-06-30'),
 'hk2025annual': dict(url='https://www.hkex.com.hk/-/media/HKEX-Market/News/News-Release/2026/260226news/260226news_eng.pdf', title='HKEX2025 annual results, page20', published='2026-02-26', evidence='root agent verified official PDF: effective2025-06-30'),
 'northbound_not_southbound': dict(url='https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-%28Stock-Connect%29/Clearing-and-Settlement?sc_lang=en', title='Stock Connect Northbound clearing/portfolio fee', published=None, evidence='read and rejected for Southbound: explicitly Northbound, not proof of Southbound portfolio fee'),
 'commission_includes_reg': dict(url='https://one.sse.com.cn/onething/gptz/', title='SSE 股票投资一件事: transaction costs', published=None, evidence='official indexed text: regulatory and handling fees included in conventional broker commission; direct reader timed out')
}


def period(name, market, start, end, rate, sources, side='both', basis='trade_notional', currency=None, **extra):
    return dict(id=f'{market}-{name}-{start}', name=name, market=market,
                route='Southbound' if market == 'HK' else 'domestic_A',
                from_inclusive=start, to_exclusive=end, fee_date_basis='execution_local_trade_date',
                timezone='Asia/Hong_Kong' if market == 'HK' else 'Asia/Shanghai',
                fee_currency=currency or ('HKD' if market == 'HK' else 'CNY'), amount_basis=basis,
                rate_decimal=rate, side=side, minimum_local='0', maximum_local=None,
                fixed_per_transaction_local='0', rounding_unit=None, rounding_mode=None,
                source_ids=sources, evidence_status='official_rate_with_historical_effective_date', **extra)


P = []
for lo, hi, rate, sources in [
 ('2015-01-01','2023-08-28','0.001',['a2022stampbase','sz2019fees']),
 ('2023-08-28',END,'0.0005',['a2022stampbase','a2023stamp'])]:
    P.append(period('stamp_duty','A_SH_SZ_BJ',lo,hi,rate,sources,side='sell'))
for lo, hi, rate, sources in [
 ('2015-01-01','2015-08-01','0.0000696',['a2015']),
 ('2015-08-01','2023-08-28','0.0000487',['a2015','a2023handling']),
 ('2023-08-28',END,'0.0000341',['a2023handling'])]:
    P.append(period('handling','A_SH_SZ',lo,hi,rate,sources))
P.append(period('handling','A_BJ','2023-08-18','2023-08-28','0.00025',['bj2023handling'],start_boundary_kind='observed_current_rate_on_announcement_day_not_original_effective_day'))
P.append(period('handling','A_BJ','2023-08-28',END,'0.000125',['bj2023handling']))
P.append(period('regulatory','A_SH_SZ','2015-01-01',END,'0.00002',['a2012reg','sz2019fees']))
P.append(period('transfer','A_SH','2015-01-01','2015-08-01','0.0003',['a2015'],basis='traded_shares_times_actual_par_value',
                implementation_status='requires_par_value_evidence_and_legacy_minimum_review'))
P.append(period('transfer','A_SZ','2015-01-01','2015-08-01','0.0000255',['a2015']))
for lo, hi, rate, source in [('2015-08-01','2022-04-29','0.00002','a2015'),('2022-04-29',END,'0.00001','a2022transfer')]:
    P.append(period('transfer','A_SH_SZ',lo,hi,rate,[source]))
for lo, hi, rate, source in [('2015-01-01','2021-08-01','0.001','hk2021stamp'),('2021-08-01','2023-11-17','0.0013','hk2021stamp'),('2023-11-17',END,'0.001','hk2023stamp')]:
    x = period('stamp_duty','HK',lo,hi,rate,[source,'southboundtax'])
    x.update(rounding_unit='1',rounding_mode='ceil',legal_aggregation='contract_note',non_HKD_quote_rule='convert to HKD with official duty FX before rounding; unavailable FX is not zero')
    P.append(x)
for lo, hi, rate in [('2015-01-01','2023-01-01','0.00005'),('2023-01-01',END,'0.0000565')]:
    x = period('trading','HK',lo,hi,rate,['hk2023trade','southboundtax']);x.update(rounding_unit='0.01',rounding_mode='nearest',legal_aggregation='per_transaction');P.append(x)
for name, lo, hi, rate, sources in [
 ('sfc_levy','2015-01-01',END,'0.000027',['hkcurrent','southboundtax']),
 ('afrc_levy','2015-01-01','2022-01-01','0',['hkcurrent','southboundtax']),
 ('afrc_levy','2022-01-01',END,'0.0000015',['hkcurrent','southboundtax']),
 ('investor_compensation_levy','2015-01-01',END,'0',['hkcurrent'])]:
    x=period(name,'HK',lo,hi,rate,sources);x.update(rounding_unit='0.01',rounding_mode='nearest',legal_aggregation='per_transaction');P.append(x)
for lo, hi, fixed in [('2015-01-01','2023-01-01','0.50'),('2023-01-01',END,'0')]:
    x=period('trading_tariff','HK',lo,hi,'0',['hk2023trade'],basis='per_exchange_transaction')
    x.update(fixed_per_transaction_local=fixed,legal_aggregation='per_transaction',pass_through_status='exchange charge; per-investor daily-fill pass-through requires declared research convention');P.append(x)
for lo, hi, rate, minimum, maximum in [('2015-01-01','2025-06-30','0.00002','2','100'),('2025-06-30',END,'0.000042','0',None)]:
    x=period('stock_settlement','HK',lo,hi,rate,['hk2025settlement','hk2025effective','hk2025annual'])
    x.update(minimum_local=minimum,maximum_local=maximum,legal_aggregation='per_exchange_transaction_per_side',
             liability_level='HKSCC participant',pass_through_status='Southbound ChinaClear participant/customer allocation not independently certified',
             historical_baseline_note='pre-change structure carried to study start; no complete2015-2025 tariff archive reviewed',
             evidence_status='official_exchange_rate; historical_baseline_and_retail_pass_through_are_declared_research_limits')
    P.append(x)

GAPS = [
 dict(id='southbound_portfolio',item='Southbound securities portfolio holding fee',status='not_verified_in_this_bounded_round',rate_decimal=None,
      reason='HKEX0.008% page is Northbound. Do not apply it to Southbound or silently charge zero.',next_action='Root may freeze a labelled economic allowance or reuse direct ChinaClear Southbound evidence; this round does not expand search.'),
 dict(id='bj_nonstamp',item='Earlier Beijing/NEEQ handling, plus regulatory and transfer schedule',status='partially_verified',rate_decimal=None,
      reason='BJ handling2023-08-28 onward is verified, preceding0.025% observed2023-08-18. Exact2022-12 cut date and earlier chain/regulatory/transfer not verified. Do not silently apply SH/SZ rates.',next_action='Separate explicit proxy decision required; raw-data pool remains intact.'),
 dict(id='sh_pre201508_par',item='Shanghai transfer basis before2015-08-01',status='rate_known_but_basis_data_incomplete',
      reason='Official0.3 per mille is on face value. Per-security par value and any legacy minimum not independently retrieved.',next_action='Use source par value if already known; otherwise label a par-value assumption, never apply0.3 per mille to trade consideration.'),
 dict(id='aggregation',item='Daily-bar order/fill granularity vs contract note and exchange transactions',status='requires_frozen_research_mapping',
      reason='Daily OHLC cannot recover exchange transaction count, broker order aggregation or all pass-through choices.',next_action='Propose one modeled fill per security/side/day; tax contract-note aggregation and brokerage minimum by order-day; publish limitation.'),
 dict(id='fx_and_corporate_action_costs',item='Southbound fee FX, currency settlement, dividend tax and corporate-action service charges',status='separate_inputs_not_completed_here',
      reason='Trade fee table does not establish dividend net tax, FX settlement spreads, action fees or payment dates.',next_action='Use explicit current-round protocol and known sources; do not subtract all cash dividends as if gross equals net.'),
 dict(id='other_jurisdictions',item='Special foreign-issuer transaction taxes and stamp exemptions',status='security_specific_unchecked',
      reason='HKEX notes potential other-jurisdiction taxes. Generic ordinary-stock schedule does not prove every listing exempt or liable.',next_action='Flag affected security when identified; no invented universal surcharge.')
]

PROPOSAL = {
 'status':'proposal_for_root_freeze_not_already_authorized_execution_policy',
 'brokerage_definition':'Net modeled broker service fee excluding separately listed statutory/exchange charges; not a quoted all-in retail commission.',
 'A_net_brokerage':dict(rate_decimal='0.0002',minimum_local='5',currency='CNY',basis='modeled_order_day',source_type='research_assumption'),
 'HK_southbound_net_brokerage':dict(rate_decimal='0.0005',minimum_local='15',currency='HKD',basis='modeled_order_day',source_type='research_assumption'),
 'slippage':dict(A_adverse_rate_decimal='0.0005',HK_adverse_rate_decimal='0.001',reference='next permitted raw open',source_type='research_assumption; no claim about actual opening liquidity'),
 'fx_spread':dict(rate_decimal='0.0005',basis='each actual currency conversion, not each mark',source_type='research_assumption; fixing/settlement dates still required'),
 'cost2':dict(proposal='Double variable transaction rates, modeled slippage and FX spread before fee rounding and min/max. Keep fixed tariff, minima/maxima and holding accrual unchanged.',
              limitation='Stress scenario only; doubled tax rates must never be labelled official historical rates. Root must freeze exact implementation before accounts.'),
 'double_count_warning':'Conventional A brokerage often includes handling/regulatory fees. Either use all-in brokerage with decomposition OR net brokerage plus explicit fees, never both totals.',
 'daily_granularity': 'One modeled fill per security/side/day; brokerage minimum by order-day; explicit research aggregation, not recovered intraday execution.'
}
PROPOSAL['sh_par_value_before_20150801'] = dict(priority='Use existing security-specific face-value evidence first',fallback_cny_per_share='1',source_type='unverified research face-value assumption',sensitivity='Report number of affected fills and resulting CNY fees; compare a larger0.1%-of-notional allowance as a stress bound, not a legal rate.')
PROPOSAL['BJ_unverified_periods'] = dict(status='root_decision_required',handling_rate_allowance_before_20230818='0.0005',regulatory_rate_allowance='0.00002',transfer_rate_allowance='0.000025',source_type='explicit economic allowances, not certified statutory schedule',limitation='Handling allowance inferred conservatively relative to two documented later reductions; not a proven historical upper bound. No implicit permission to trade pre-BSE NEEQ history.')
for p in P:
    p.setdefault('start_boundary_kind', 'study_window_clip_not_original_introduction' if p['from_inclusive']=='2015-01-01' else 'stated_effective_date')
    if p['market']=='A_SH_SZ' and p['name']=='handling' and p['from_inclusive']=='2023-08-28':
        p['source_ids'].append('bj2023handling')

data = dict(schema_version=1, created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
            status='bounded_primary_source_evidence_and_unfrozen_research_defaults', study_start='2015-01-01', study_end_exclusive=END,
            decimal_semantics='rate_decimal is a fraction of amount, not percent; 0.0005 means0.05% or5bps.',
            periods=P, holding_fee_periods=[], gaps=GAPS, research_defaults_proposal=PROPOSAL, sources=SOURCES,
            no_future_extension='Do not use dated final intervals after2026-10-22 without review.',
            excluded_claims=['complete Southbound retail settlement fee history','BJ fee history','broker-specific execution cost','dividend-tax completeness'],
            account_runs=0, algorithm_changes=0)
with (OUT/'fees.json').open('x') as f: json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
manifest=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(OUT.glob('source-read-*.txt'))]
with (OUT/'source-manifest.json').open('x') as f:json.dump(manifest,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'periods':len(P),'sources':len(SOURCES),'gaps':len(GAPS),'account_runs':0}))
