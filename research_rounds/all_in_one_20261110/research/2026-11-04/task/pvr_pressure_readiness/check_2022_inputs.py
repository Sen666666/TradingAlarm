"""2022 input/initial state/MRO/calendar readiness only; zero account events."""
import json,time,traceback
from pathlib import Path
import technical_checks as T
A,N,J,S=T.A,T.N,T.J,T.S
def main():
    started=time.monotonic();assert not(T.O/'INPUT_2022_GATE.json').exists()
    N.configure_scores();shared,receipts,cp,states,ir,identity=A.read_inputs('2022')
    kw=S.kwargs(cp,states,ir);h=dict(start='2022-01-01',end='2022-12-30',input_identity=S.canonical_identity(identity),scope='original2022 full inputs')
    result={}
    for mode in ('cost2_OFF','cost2_ON','D1_OFF','D1_ON'):
        r=T.construct(mode,shared,receipts,kw,h);a=r.accounts['B']
        assert a.initial_cash==a.available==J.D(1000000) and not a.trades and not a.positions and not a.buys and not a.pending
        assert not r.daily and not r.funding and not r.opportunities
        p=dict(native_account_events=0,fresh_cash='1000000',empty_financial_book=True,warm_industry_state_preserved=True)
        if mode.startswith('D1'):
            # Calendar is an execution input, unlike future market prices/signals.
            last=J.M.N.iso('2022-12-30T09:30:00+08:00');nextsession=a.next_session(last)
            assert str(nextsession.date())>'2022-12-30'
            p['last_session_retry_calendar_covered']=str(nextsession)
        result[mode]=p
    T.save('INPUT_2022_GATE.json',dict(passed=True,source_sha256=N.sha(__file__),input_identity=S.canonical_identity(identity),
        modes=result,seconds=time.monotonic()-started,full_economic_paths=0,account_events=0,
        limit='construction only; no2022 cost or D1 path outcome tested'))
if __name__=='__main__':
    try:main()
    except BaseException as e:T.save('INPUT_2022_FAILURE.json',dict(reason=str(e),traceback=traceback.format_exc()));raise
