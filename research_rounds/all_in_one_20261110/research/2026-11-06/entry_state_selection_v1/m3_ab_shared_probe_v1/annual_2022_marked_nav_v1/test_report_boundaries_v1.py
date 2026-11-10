from pathlib import Path
from decimal import Decimal as D
import sys,copy,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import marked_nav_v1 as M
def main():
    rows=[dict(day='2022-01-04',phase='CLOSE',reconciliation=dict(NAV='1200000',certified=True,unknown=[])),
          dict(day='2022-12-29',phase='CLOSE',reconciliation=dict(NAV='1188000',certified=True,unknown=[])),
          dict(day='2022-12-30',phase='OPEN',reconciliation=dict(NAV=None,certified=False,unknown=[dict(sid='UNKNOWN')],NAV_gap_reason='ASSET_OR_SOURCE_UNKNOWN'))]
    a,_=M.stats(rows)
    assert not a['year_end_reached'] and a['last_completed_close']=='2022-12-29'
    assert a['annual_endpoint_return'] is None and a['annual_marked_close_maximum_drawdown'] is None
    assert a['observed_prefix_endpoint_return']==D('-.01')
    rows[-1]['phase']='CLOSE'
    a,_=M.stats(rows)
    assert a['year_end_reached'] and a['last_completed_close']=='2022-12-30'
    assert a['annual_endpoint_return'] is None and a['annual_marked_close_maximum_drawdown'] is None
    for change in [dict(certified=False,unknown=[]),dict(certified=True,unknown=[dict(sid='X')])]:
        row=copy.deepcopy(rows[0]);row['reconciliation'].update(change)
        try:M.marked_row(row)
        except ValueError:pass
        else:raise AssertionError('contradictory certified NAV accepted')
    result=dict(status='PASS',groups=['OPEN_stop_uses_prior_completed_CLOSE_only','Dec30_CLOSE_UNKNOWN_year_end_reached_but_both_annual_metrics_null','certified_NAV_contradiction_rejected'],economic_calls=0)
    with (HERE/'REPORT_BOUNDARY_QA.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
if __name__=='__main__':main()
