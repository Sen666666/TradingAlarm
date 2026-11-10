"""Explicit research data audit closeout, preserving remaining unknown identities."""
from build_inputs import HERE,OLD,read,write,ref,sha256,now

def main():
 report=read(HERE/'audit/data-independent-v1/report.json');summary=read(HERE/'data-adjudicated-v2/summary.json')
 assert report['independent_errors']==0 and report['qualified']==1709 and not report['qualified_unresolved']
 assert {x['symbol'] for x in report['all_roster_unresolved']}=={'002731.SZ'}
 assert summary['raw_roster']==summary['with_bars']==5576 and summary['rights_status_counts']=={'received_current':5576}
 assert set(report['unknown_cap_retained'])=={'000016.SZ','002731.SZ'}
 assert read(HERE/'audit/data-independent-v1/current-cap-integrity.json')['rows_checked']==5576
 assert read(HERE/'audit/algorithm-registry-check.json')['mismatches']==[]
 construction=read(HERE/'inputs-v1/construction-summary.json')
 assert construction['stocks_retained']==1711 and construction['sectors']==90
 files=[HERE/'data-adjudicated-v2/coverage.csv',HERE/'data-adjudicated-v2/unresolved.csv',
  HERE/'data-adjudicated-v2/summary.json',HERE/'data-adjudicated-v2/adjudications.json',
  HERE/'data-finalized-v1/conflicts.csv',HERE/'data-finalized-v1/summary.json',HERE/'source-view-v1/sources.json',
  HERE/'audit/data-independent-v1/report.json',HERE/'audit/data-independent-v1/errors.json',
  HERE/'audit/data-independent-v1/price-observation-audit.json',HERE/'audit/data-independent-v1/current-cap-integrity.json',
  HERE/'audit/bse-listing-facts.json',HERE/'downloads/current-cap-all/snapshot.json',HERE/'inputs-v1/selection.json',
  HERE/'inputs-v1/roster-dispositions.json',HERE/'inputs-v1/action-normalization.json',HERE/'inputs-v1/construction-summary.json',
  HERE/'PROTOCOL.md',HERE/'audit/algorithm-registry-check.json']
 receipt=HERE/'audit/data-closeout.json'
 if receipt.exists():raise ValueError('Receipt already frozen')
 write(receipt,dict(kind='data_closeout',round_id=HERE.name,status='data_pool_closed',scope_date='2026-10-22',
  scope_sha256=sha256(HERE/'scope.json'),recorded_at=now(),artifacts={str(p.relative_to(receipt.parent)) if p.is_relative_to(receipt.parent) else '../'+str(p.relative_to(HERE)):sha256(p) for p in files},
  closure_meaning='All-roster collection and audit disposition closed for this fixed research input; NOT all unknowns resolved, precise rights ledger or PIT universe certified.',
  raw_roster=5576,raw_rows=summary['rows'],strategy_cap_qualified=1709,explicit_unknown_cap_lines=report['unknown_cap_retained'],
  remaining_unknown_source_origin='002731.SZ; cannot be admitted because cap unknown; retained in raw and strategy evidence, no exclusion by returns',
  last_source_before_target=7,qualified_last_before_target={'601326.SH':'2026-10-20; last source mark retained as stale, no fictitious Oct21/22 executable bar'},
  corporate_actions='Explicit declared proxy terms; 65 empty qualified responses are no-supported-events assumption, not certified no events; exact cash pay dates unknown.',
  economic_accounts_run=0,algorithm_changes=0))
 manifest=read(HERE/'inputs-v1/manifest-before-closeout.json');manifest['data_pool_closeout']=ref(receipt)
 write(HERE/'inputs-v1/input-manifest.json',manifest)
 print({'status':'data_pool_closed','qualified':1709,'explicit_unknown_cap':2,'sectors':90,'economic_accounts_run':0},flush=True)

if __name__=='__main__':main()
