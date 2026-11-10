"""Saved completed full-run clock/source audit, with no engine import/replay."""
from pathlib import Path
from collections import Counter
import argparse,gzip,hashlib,json
import pandas as pd

O=Path(__file__).resolve().parent;T=O.parent/'market_gross_admission_native_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt')as f:
        for s in f:yield json.loads(s)
def timestamp(x):return pd.Timestamp(x).isoformat()
def info_norm(v):
    v=dict(v)
    if v.get('available_at')is not None:v['available_at']=timestamp(v['available_at'])
    return v

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['long','strong'],required=True)
    args=ap.parse_args();run=T/('full-'+args.window+'-v1');prep=T/'prepared'/args.window
    assert(run/'DONE.json').is_file()and(run/'WINDOW_RESULT.json').is_file(),'wait for committed full window'
    out=O/('full-'+args.window+'-actual-clock-v1');assert not out.exists();out.mkdir()
    result=read(run/'WINDOW_RESULT.json');started=read(run/'STARTED.json');done=read(run/'DONE.json')
    manifest=read(prep/'FULL_SOURCE_MANIFEST.json');authpath=Path(started['authorization']);auth=read(authpath)
    assert started['full_schema']==manifest
    assert auth['approved']is True and auth['source_manifest_SHA256']==sha(prep/'FULL_SOURCE_MANIFEST.json')
    assert started['authorization_sha256']==sha(authpath)
    assert auth['authorized_executed_arms']==manifest['executed_arms']==result['executed_arms']==['D_GROSS10']
    assert auth['archived_No60_control_not_rerun']is True and manifest['financial_control_rerun']is False
    assert auth['initial_capital_CNY']==manifest['initial_CNY']=='1000000'
    assert manifest['market_gross_alpha']=='.10'and manifest['old_ACT20_BREAK63']is True
    assert manifest['provider']=='market_info_v2.MarketInfo'and manifest['cost_guard_or_new_ledger']is False
    assert done['completed']is True and set(done['ending_NAV'])=={'D_GROSS10'}
    assert result['source_post_exact']is True and result['days']==manifest['closes']
    mismatched=[]
    for p,h in manifest['sources'].items():
        if sha(p)!=h:mismatched.append(p)
    assert not mismatched,('full frozen source changed',mismatched)
    calpath=prep/'EXPECTED_CLOSE_CALENDAR.json';clockpath=prep/'MARKET_INFO_FULL_CLOCKS.json'
    cal=read(calpath);proof=read(clockpath)
    assert proof['expected_calendar_sha256']==sha(calpath)
    history=Path(manifest['stored_info_path']);history_sha=sha(history);assert proof['source_history_sha256']==history_sha
    # The full planned-clock/CSV comparison already has an independent receipt;
    # consume its exact frozen map, without recalculating any stock or ETF MA.
    previous=read(O/'FULL_PREPARATION_REVIEW_GATE.json')
    assert previous['passed']is True and previous['full_source_manifest_SHA256'][args.window]==sha(prep/'FULL_SOURCE_MANIFEST.json')
    scheduled={timestamp(r['at']):info_norm({k:v for k,v in r.items()if k!='at'})for r in proof['all_scheduled_OPEN_CLOSE']}
    assert len(scheduled)==2*manifest['closes']
    info_fields={'day','available_at','X','MA63','previous_MA63','state','source','source_sha256'}
    eventpath=run/'pair/gross-admission-events.jsonl.gz';kinds=Counter();states=Counter();unique={};raw_info={};n=0
    allowed_kinds={'route','reserve_pre','reserve_post','fill_pre','fill_post','fill_cancelled'}
    for e in rows(eventpath):
        assert e['sequence']==n;n+=1
        assert e['kind']in allowed_kinds;kinds[e['kind']]+=1
        if 'account'in e:assert e['account']=='D_GROSS10'
        at=timestamp(e['at']);assert at in scheduled,('event outside frozen native clock',at)
        expected=scheduled[at];info=e['info'];assert set(info)==info_fields
        if at not in unique:
            actual=info_norm(info);assert actual==expected,('actual provider value/asof mismatch',at)
            assert actual['source']==str(history.resolve())and actual['source_sha256']==history_sha
            assert pd.Timestamp(actual['available_at'])<=pd.Timestamp(at)
            if pd.Timestamp(at).hour<15:assert actual['day']<at[:10],'OPEN read its own future CLOSE'
            unique[at]=dict(info=actual,event_counts=Counter());raw_info[at]=info
        else:assert info==raw_info[at],('same clock actual info changed',at)
        states[info['state']]+=1;unique[at]['event_counts'][e['kind']]+=1
    assert states['UNKNOWN']==0,'all full source clocks were certified known; investigate any unknown actual callback'
    # Native output has one actually executed account; archived B remains an xref.
    book_names=sorted(p.name for p in (run/'pair').glob('*.json.gz'))
    assert book_names==['D_GROSS10.json.gz'],('unexpected new native book/B execution',book_names)
    daily=list(rows(run/'pair/daily.jsonl.gz'));assert len(daily)==manifest['closes']
    assert {r['account']for r in daily}=={'D_GROSS10'}
    dates=[str(r['at'])[:10]for r in daily]
    assert dates==[str(x)[:10]for x in cal['closes'][2:]]
    assert result['archived_control_xref']==manifest['archived_B_only_xref']
    refs=[run/'STARTED.json',run/'DONE.json',run/'WINDOW_RESULT.json',run/'pair/daily.jsonl.gz',eventpath,
          prep/'FULL_SOURCE_MANIFEST.json',calpath,clockpath,authpath,O/'FULL_PREPARATION_REVIEW_GATE.json',O/'PROVIDER_CLOCK_INDEPENDENT_REVIEW.json']
    output=dict(passed=True,status='PASS_COMPLETED_FULL_ACTUAL_GROSS_EVENT_INFO_CLOCK_SOURCE_AND_SINGLE_ACCOUNT_SCOPE',window=args.window,
        full_native_CLOSEs=manifest['closes'],full_planned_OPEN_CLOSEs=len(scheduled),all_actual_gross_events=n,unique_actual_clock_infos=len(unique),event_kind_counts=dict(kinds),actual_event_state_counts=dict(states),
        all_event_asof_values_source_D_match_frozen_full_clock_exact=True,next_OPEN_never_uses_today_CLOSE=True,
        actual_UNKNOWN_domain_events=0,UNKNOWN_fail_closed_scope='Provider negative-domain checks have separate zero-account receipt; no native unknown fill claimed.',
        only_D_GROSS10_native_book_and_daily=True,archived_B_control_not_executed=True,single_alpha='.10',old_ACT_BREAK_exit_fee_sources_unchanged=True,
        all_frozen_sources_post_exact=len(manifest['sources']),source_manifest_SHA256=sha(prep/'FULL_SOURCE_MANIFEST.json'),
        actual_unique_clock_info=[dict(at=at,**v['info'],event_counts=dict(v['event_counts']))for at,v in sorted(unique.items())],
        evidence_SHA256={str(p.resolve()):sha(p)for p in refs},checker_SHA256=sha(__file__),
        accounts_or_economic_replays_by_reviewer=0,MA_TR_recomputation=0,private_score_or_atomic_financial_reaudit=False,economic_promotion=False,
        limits=['Financial I/R/NAV/fees/PVR atomic checks and phase wealth are separate independent owners.',
            'No future price, completed outcome label or stock indicator is recomputed/inserted.',
            'Source and clock pass certify actual frozen implementation, not strategy efficacy or risk-return acceptance.'])
    path=out/'ACTUAL_CLOCK_SOURCE_REVIEW.json';path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:output[k]for k in ['passed','window','full_native_CLOSEs','all_actual_gross_events','unique_actual_clock_infos','event_kind_counts','actual_event_state_counts','source_manifest_SHA256']},indent=2))
    print('RECEIPT',path,sha(path))

if __name__=='__main__':main()
