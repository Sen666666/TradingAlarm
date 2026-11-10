"""Reporting-only valuation. Never changes engine state, cash, fills, risk or CP."""
from decimal import Decimal as D
ALLOWED_GAPS=frozenset(('KNOWN_HALT_STALE_MARK','RESUME_OPEN_RECOVERY_LOCK'))
def marked_row(row):
    r=row['reconciliation']
    nav=r.get('NAV');gap=r.get('NAV_gap_reason')
    supported=False
    if nav is not None:
        if not r.get('certified') or r.get('unknown'):raise ValueError('Inconsistent certified NAV')
        basis='CURRENT_RAW_MARK'
    elif gap in ALLOWED_GAPS and not r.get('unknown') and r.get('indicative_NAV_NOT_CERTIFIED') is not None:
        nav=r['indicative_NAV_NOT_CERTIFIED'];supported=True
        basis='LAST_VALID_CLOSE_KNOWN_FULL_DAY_HALT' if gap=='KNOWN_HALT_STALE_MARK' else 'CURRENT_RAW_OPEN_RISK_RECOVERY_LOCK'
        if gap=='KNOWN_HALT_STALE_MARK' and not r.get('stale_marks'):raise ValueError('Halt mark lacks provenance')
    else:basis='UNKNOWN_NO_IMPUTATION'
    if nav is not None and (not D(str(nav)).is_finite() or D(str(nav))<=0):raise ValueError('Invalid marked NAV')
    return dict(day=str(row['day'])[:10],phase=row['phase'],marked_NAV=None if nav is None else str(nav),
        valuation_basis=basis,marked_value_available=nav is not None,supported_indicative_substitution=supported,
        stale=bool(r.get('NAV_stale')),stale_marks=r.get('stale_marks',[]),gap_reason=gap,unknown=r.get('unknown',[]),
        engine_NAV=r.get('NAV'),engine_certified=bool(r.get('certified')),new_risk_allowed=r.get('new_risk_allowed'),
        risk_recovery_pending=r.get('risk_recovery_pending'),gross_mark_without_hypothetical_sell_fee=True)
def stats(rows,expected_end='2022-12-30',seed='1200000'):
    curve=[marked_row(r) for r in rows];cl=[r for r in curve if r['phase']=='CLOSE']
    if not cl:raise ValueError('No completed CLOSE')
    end=cl[-1];gaps=[r for r in cl if r['marked_NAV'] is None]
    contiguous=not gaps
    annual_end=end['day']==expected_end
    endpoint=None if end['marked_NAV'] is None else D(end['marked_NAV'])/D(seed)-1
    maximum_drawdown=None;peak_day=None;trough_day=None
    if contiguous:
        peak=D(seed);peak_date=cl[0]['day'];dd=D(0)
        for row in cl:
            value=D(row['marked_NAV'])
            if value>peak:peak=value;peak_date=row['day']
            loss=value/peak-1
            if loss<dd:dd=loss;peak_day=peak_date;trough_day=row['day']
        maximum_drawdown=dd
    return dict(observation_start=cl[0]['day'],expected_annual_end=expected_end,last_completed_close=end['day'],
        year_end_reached=annual_end,annual_endpoint_return=endpoint if annual_end else None,
        annual_marked_close_maximum_drawdown=maximum_drawdown if annual_end and contiguous else None,
        observed_prefix_endpoint_return=endpoint,observed_prefix_marked_close_maximum_drawdown=maximum_drawdown,
        drawdown_peak_day=peak_day,drawdown_trough_day=trough_day,
        denominator_seed=D(seed),last_close_marked_NAV=end['marked_NAV'],complete_marked_close_path=contiguous,
        close_observations=len(cl),unresolved_close_gaps=gaps,
        supported_stale_close_count=sum(r['stale'] for r in cl),supported_stale_phase_count=sum(r['stale'] for r in curve),
        valuation_convention='Cash + gross raw CLOSE inventory + recognized receivables; proven full-day halts use last valid CLOSE; no hypothetical liquidation fee',
        risk_and_trade_state_unchanged=True,not_current_liquidatable_NAV=any(r['stale'] for r in cl),
        no_forward_filling_unproven_missing_prices=True,no_annualization=True),curve
