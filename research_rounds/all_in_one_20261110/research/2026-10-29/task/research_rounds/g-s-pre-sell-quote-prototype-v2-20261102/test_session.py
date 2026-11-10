"""Only quote-clock regression. No account/runner/event is created."""
from pathlib import Path
import copy,json,sys,hashlib
import quote_package as P
from prepare_cases import O,load,save
from test_quote import fixture

def unknown(name,x):
    before=P.digest(x);r=P.proposal(x,expected_sha256=before)
    assert r['state']=='UNKNOWN' and r['Q'] is None and r['D'] is None
    assert r['freeze_quantity_caps'] is False and r['receipt_consumed'] is False
    assert r['actual_releases']=={'cash':'0','risk':'0'} and P.digest(x)==before
    save(O/'session-results'/(name+'.json'),r);return r

def main():
    audit=Path('/tmp/pre-sell-quote-independent-20261102')
    old=load(audit/'stale_timestamp_counterexample_INPUT.json')
    cases={};cases['independent_previous_day']=unknown('independent_previous_day',old)['state']
    future=fixture();future['quotes']['B']['known_at']='2025-07-03T09:30:00+08:00'
    cases['future']=unknown('future',future)['state']
    for name,value in [('unknown_None',None),('unknown_naive','2025-07-02T09:30:00'),('unknown_malformed','unknown')]:
        x=fixture();x['quotes']['B']['known_at']=value;cases[name]=unknown(name,x)['state']
    missing=fixture();del missing['quotes']['B']['known_at'];cases['missing_clock']=unknown('missing_clock',missing)['state']
    contradiction=fixture();contradiction['quote_session']='2025-07-01'
    cases['declared_session_contradiction']=unknown('declared_session_contradiction',contradiction)['state']
    valid=fixture();r=P.proposal(valid,expected_sha256=P.digest(valid));assert r['Q']['B']==499
    save(O/'session-results/current_valid.json',r);cases['current_valid']=r['state']
    # Same real instant as Shanghai Jul2 09:30, represented with a Jul1 date.
    offset=fixture();offset['at']='2025-07-01T20:30:00-05:00';offset['quotes']['B']['known_at']='2025-07-01T20:30:00-05:00'
    z=P.proposal(offset,expected_sha256=P.digest(offset));assert z['Q']==r['Q'] and z['D']==r['D']
    save(O/'session-results/current_other_offset.json',z);cases['current_other_offset']=z['state']
    # Pure date conversion boundary, not a claim that an A-share opening print
    # exists at 00:30. UTC July1 belongs to Shanghai trading date July2.
    assert P.exchange_session_day('2025-07-01T16:30:00+00:00')=='2025-07-02'
    assert P.exchange_session_day('2025-07-01T15:59:00+00:00')=='2025-07-01'
    assert P.EXCHANGE_TIMEZONE=='Asia/Shanghai'
    base=O.parent/'g-s-pre-sell-quote-prototype-v1-20261102';same={}
    for p in (base/'results').glob('*.json'):
        new=O/'results'/p.name
        assert new.exists(),p.name
        same[p.name]=json.loads(p.read_text())==json.loads(new.read_text())
        assert same[p.name],('original behavior changed',p.name)
    immutable=json.loads((O/'V1_IMMUTABLE_BASELINE.json').read_text())
    for path,h in immutable.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
    save(O/'SESSION_REGRESSION.json',dict(passed=True,financial_events=0,session_timezone=P.EXCHANGE_TIMEZONE,
        fixed_counterexample=cases,old_six_groups_and_15_outputs_exact=same,v1_all_54_files_unchanged=True,
        audit_sha256=hashlib.sha256((audit/'FINAL_AUDIT.json').read_bytes()).hexdigest(),clock_boundary_test_not_market_execution=True))
    print('SESSION_REGRESSION_PASS',len(cases),'clock cases;',len(same),'v1 outputs exact; financial events 0',flush=True)
if __name__=='__main__':main()
