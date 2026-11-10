"""Offline inventory audit. Never converts collector completion into economic approval."""
from __future__ import annotations
import argparse, collections, csv, datetime, hashlib, json
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def records(path):
    path=Path(path)
    if path.suffix=='.json':
        x=json.loads(path.read_text())
        if not isinstance(x,list):raise ValueError(f'Expected row-list manifest: {path}')
        return x
    with path.open(newline='') as f:return list(csv.DictReader(f))


def keyed(rows,label):
    result={}
    for row in rows:
        symbol=row.get('symbol')
        if not symbol or symbol in result:raise ValueError(f'{label}: missing/duplicate symbol {symbol!r}')
        result[symbol]=row
    return result


def integer(row,key):
    value=row.get(key)
    return None if value in (None,'') else int(value)


def artifact(path,expected):
    if not path:return 'absent_reference'
    p=Path(path)
    if not p.is_file():return 'missing_file'
    if not expected:return 'missing_expected_hash'
    return 'verified' if sha(p)==expected else 'hash_mismatch'


def audit_rows(master,manifests,sectors,snapshot,check_artifact=artifact):
    """Left join only. Classification describes evidence, not trading permissions."""
    mm=keyed(master,'master');fm=keyed(manifests,'A/H manifests')
    ss=keyed(sectors,'sector coverage');cc=keyed(snapshot,'snapshot selection');out=[]
    for sid,m in mm.items():
        f=fm.get(sid,{});cap=cc.get(sid,{});issues=[]
        n=integer(f,'rows') or 0;p=integer(f,'price_eligible_rows');bad=integer(f,'invalid_price_rows')
        missing=integer(f,'missing_volume_rows');positive=integer(f,'positive_volume_rows')
        unresolved=integer(f,'unresolved_source_failures')
        if any(v is not None and (v<0 or v>n) for v in [p,bad,missing,positive]):
            issues.append('manifest_row_counts_invalid')
        if p is not None and bad is not None and p+bad!=n:issues.append('price_counts_do_not_partition_raw')
        bar_status=check_artifact(f.get('bars_path',''),f.get('bars_sha256',''))
        signal_status=check_artifact(f.get('signal_bars_path',''),f.get('signal_bars_sha256',''))
        action_status=check_artifact(f.get('rights_path',''),f.get('rights_sha256',''))
        if not f:raw='manifest_missing';issues.append('manifest_missing')
        elif unresolved is None:raw='source_dispositions_not_reported';issues.append(raw)
        elif unresolved:raw='unresolved_source_attempts';issues.append(raw)
        elif not (integer(f,'accepted_new_sources') or 0):raw='no_accepted_current_history';issues.append(raw)
        elif n<=0:raw='no_raw_observations';issues.append(raw)
        elif bar_status!='verified':raw='raw_artifact_unverified';issues.append(raw)
        else:raw='current_raw_observations_verified'
        start=f.get('start_status','missing');tail=f.get('tail_status','missing')
        start_ok=start in ('reaches_start','available_source_start_verified')
        tail_ok=tail in ('end_reached','latest_source_bar_before_end_suspension_or_source_limit')
        boundary='documented_available_source_bounds' if start_ok and tail_ok else 'unconfirmed_source_bounds'
        if boundary=='unconfirmed_source_bounds':issues.append(boundary)
        if tail=='latest_source_bar_before_end_suspension_or_source_limit':issues.append('tail_reason_not_established')
        if p is None:price='price_count_missing'
        elif not p:price='no_valid_price_observations'
        elif bar_status!='verified' or signal_status!='verified':price='price_artifact_unverified'
        elif 'manifest_row_counts_invalid' in issues or 'price_counts_do_not_partition_raw' in issues:price='price_counts_invalid'
        else:price='valid_prices_with_quarantined_rows' if bad else 'valid_price_observations_present'
        if not price.startswith('valid_price'):issues.append(price)
        # No inference that missing=0 means every date has positive real volume.
        if not n:volume='no_raw_observations'
        elif missing is None:volume='volume_diagnostics_missing'
        elif missing:volume='missing_volume_prices_preserved'
        elif positive is None:volume='no_missing_volume_reported_positive_count_unknown'
        else:volume='positive_and_nonpositive_counts_available'
        rights=f.get('rights_status','missing')
        actions='raw_received_ledger_not_certified' if rights=='received_current' and action_status=='verified' else 'raw_actions_unverified'
        if actions=='raw_actions_unverified':issues.append(actions)
        sector_id=m.get('industry_index_symbol','');sector=ss.get(sector_id,{})
        if not sector_id:industry='mapping_missing'
        elif not sector:industry='sector_coverage_missing'
        elif not (integer(sector,'price_eligible_rows') or 0):industry='sector_prices_missing'
        elif str(sector.get('end_reached','')).lower()!='true':industry='sector_tail_unconfirmed'
        elif (integer(sector,'source_overlap_conflict_cells') or 0)>0:industry='sector_source_conflict'
        else:industry='mapped_sector_price_observations_present'
        if industry!='mapped_sector_price_observations_present':issues.append(industry)
        cap_status=cap.get('strategy_snapshot_filter_status','missing') if cap else 'snapshot_row_missing'
        if not cap:issues.append('snapshot_row_missing')
        if cap and cap.get('industry_index_symbol')!=sector_id:issues.append('master_snapshot_industry_disagreement')
        if m.get('snapshot_date')!='2026-10-22':issues.append('master_snapshot_date_mismatch')
        if cap and cap.get('snapshot_date')!='2026-10-22':issues.append('cap_snapshot_date_mismatch')
        out.append(dict(symbol=sid,name=m.get('name',''),market='H' if sid.endswith('.HK') else 'A',
            ths_symbol=m.get('ths_symbol',''),master_snapshot_date=m.get('snapshot_date',''),
            raw_collection=raw,source_boundary=boundary,price=price,volume=volume,actions=actions,snapshot=cap_status,industry=industry,
            raw_rows=n,first=f.get('first',''),last=f.get('last',''),source_start_status=start,source_tail_status=tail,
            price_eligible_rows=p,invalid_price_rows=bad,missing_volume_rows=missing,positive_volume_rows=positive,
            zero_volume_observed_bars=integer(f,'zero_volume_observed_bars'),
            accepted_new_sources=integer(f,'accepted_new_sources'),rejected_new_sources=integer(f,'rejected_new_sources'),
            unresolved_source_failures=unresolved,resolved_source_failures=integer(f,'resolved_source_failures'),
            bars_path=f.get('bars_path',''),bars_sha256=f.get('bars_sha256',''),raw_artifact=bar_status,signal_artifact=signal_status,
            volume_unit=f.get('volume_unit',''),amount_unit=f.get('amount_unit',''),unit_crosscheck_status=f.get('unit_crosscheck_status',''),
            currency_basis=f.get('currency_basis',m.get('currency_basis','')),historical_currency_certified=False,
            rights_status=rights,rights_records=integer(f,'rights_records'),rights_unparsed=integer(f,'rights_unparsed'),
            rights_path=f.get('rights_path',''),rights_sha256=f.get('rights_sha256',''),rights_artifact=action_status,
            action_ledger_certified=False,industry_index_symbol=sector_id,sector_rows=integer(sector,'rows'),
            sector_price_rows=integer(sector,'price_eligible_rows'),sector_positive_volume_rows=integer(sector,'positive_volume_rows'),
            sector_price_rows_without_positive_volume=integer(sector,'price_rows_missing_or_nonpositive_volume'),
            sector_continuity_status=sector.get('continuity_status',''),
            company_market_cap_cny=cap.get('company_market_cap_cny',''),company_cap_status=cap.get('company_market_cap_status',''),
            size_filter_status=cap.get('size_filter_status','missing'),southbound_filter_status=cap.get('southbound_filter_status','missing'),
            industry_filter_status=cap.get('industry_filter_status','missing'),security_type_filter_status=cap.get('security_type_filter_status','missing'),
            current_pool_only=True,economic_input_ready=False,issues=issues))
    return out,{'manifest_symbols_outside_master':sorted(set(fm)-set(mm)),
                'snapshot_symbols_outside_master':sorted(set(cc)-set(mm)),
                'manifest_missing_master_symbols':sorted(set(mm)-set(fm)),
                'snapshot_missing_master_symbols':sorted(set(mm)-set(cc))}


def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['master','a-manifest','h-manifest','sector-coverage','snapshot','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--queue-state',type=Path,action='append',default=[])
    a=p.parse_args();input_paths=[a.master,a.a_manifest,a.h_manifest,a.sector_coverage,a.snapshot,*a.queue_state]
    before={str(x.resolve()):sha(x) for x in input_paths}
    master=records(a.master);manifests=records(a.a_manifest)+records(a.h_manifest)
    rows,identity=audit_rows(master,manifests,records(a.sector_coverage),records(a.snapshot))
    queues=[dict(path=str(x.resolve()),status=json.loads(x.read_text()).get('status','unknown')) for x in a.queue_state]
    terminal='unknown_no_queue_evidence' if not queues else 'all_specified_queues_finished' if all(x['status']=='finished' for x in queues) else 'some_specified_queues_not_finished'
    # This detects mutation while reading; no assertion that supplied queues are exhaustive.
    if any(sha(x)!=before[str(x.resolve())] for x in input_paths):raise ValueError('An input changed during audit; no output published')
    a.out.mkdir(parents=True,exist_ok=False)
    with (a.out/'securities.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['symbol']);w.writeheader()
        for row in rows:w.writerow(dict(row,issues=json.dumps(row['issues'],ensure_ascii=False)))
    write_json(a.out/'identity-audit.json',identity)
    summary=dict(master_securities=len(master),reported_securities=len(rows),market_counts=dict(collections.Counter(x['market'] for x in rows)),
        dimensions={key:dict(collections.Counter(x[key] for x in rows)) for key in ['raw_collection','source_boundary','price','volume','actions','snapshot','industry']},
        supplied_queue_status=terminal,supplied_queues=queues,all_expected_queues_certified=False,
        data_pool_economic_ready=False,action_ledger_certified=False,algorithm_changed=False,account_runs=0,network_requests=0,
        caveat='Current 2026-10-22 survivor-pool inventory only. Selection failures remain rows. Available source start is not listing date; raw rights are not a certified ledger; missing volume does not erase valid prices.')
    write_json(a.out/'summary.json',summary)
    write_json(a.out/'input-manifest.json',dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=before,
        code={str(Path(__file__).resolve()):sha(__file__)},scope_end='2026-10-22',scope_start='2013-01-01'))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
