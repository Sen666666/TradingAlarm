"""Independent accounting of saved state/event evidence; no model rerun or download."""
from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results/v0'
def main():
    ranking=pd.read_csv(OUT/'ranking.csv');mt=pd.read_csv(OUT/'event-matches.csv');ep=pd.read_csv(OUT/'episodes.csv');target=json.loads((HERE/'targets.json').read_text());fr=json.loads((HERE/'fit-protocol.json').read_text())
    # Decode the saved source afresh, independently of the network collector.
    raw=(HERE/'raw/sina-AU0.response').read_text();rr=json.loads(raw.split('=(',1)[1].rsplit(');',1)[0])
    src=pd.DataFrame(rr).rename(columns={'d':'date','o':'open','h':'high','l':'low','c':'close','v':'volume','p':'hold','s':'settle'})
    src=src[['date','open','high','low','close','volume','hold','settle']];src['date']=pd.to_datetime(src.date)
    src=src.set_index('date').sort_index().astype(float).loc['2024-01-01':'2026-10-23']
    saved=pd.read_csv(HERE/'data/sina-AU0.csv',index_col='date',parse_dates=True).astype(float)
    pd.testing.assert_frame_equal(src,saved,check_index_type=False,check_freq=False)
    checks=[];atr_cycles=0
    for row in ranking.itertuples():
        s=pd.read_parquet(OUT/'daily'/(row.model+'.parquet'))
        pulses=s.entered.astype(int)-s.exited.astype(int)
        np.testing.assert_array_equal(pulses.cumsum().to_numpy(),s.target.to_numpy())
        assert not (s.entered.astype(bool)&s.exited.astype(bool)).any()
        z=s.loc['2025-01-01':target['alignment']['inferred_last_date']]
        assert z.entered.sum()==row.starts and z.exited.sum()==row.ends and z.target.sum()==row.active_days
        q=mt.loc[mt.model.eq(row.model)];matched=q.loc[q.action.eq('match')]
        assert len(matched)+q.action.eq('extra').sum()==row.starts+row.ends
        assert len(matched)+q.action.eq('missing').sum()==10
        assert q.loc[q.target_id.notna(),'target_id'].nunique()==10
        actual=matched.outside_band.sum()+30*(q.action.eq('extra').sum()+q.action.eq('missing').sum())
        assert actual==row.event_edit_cost
        assert matched.outside_band.eq(0).sum()==row.within_target_band
        for kind in ['start','end']:
            r=matched.loc[matched.kind.eq(kind)];assert r.predicted_index.is_monotonic_increasing and r.target_index.is_monotonic_increasing
        if row.model.startswith(('trail-','volume-trail-')):
            cycle=(s.entered.cumsum()).where(s.target.eq(1))
            for _,group in s.loc[s.target.eq(1)].groupby(cycle.dropna()):
                assert group.floor.diff().dropna().ge(-1e-10).all()
                assert group.close.gt(group.floor).all();atr_cycles+=1
        checks.append(dict(model=row.model,state_event_conservation=True,all_events_in_score=True))
    for p,h in fr['original_code'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),saved_AU0_rows_reparsed=len(saved),saved_state_series=len(checks),state_event_and_score_checks=checks,ATR_monotonic_cycles=atr_cycles,old_code_hashes_unchanged=True,accounts=0)
    (OUT/'independent-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Independent audit passed',len(checks),'series',atr_cycles,'ATR cycles')
if __name__=='__main__':main()
