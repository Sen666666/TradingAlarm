"""Bounded read-only local membership/history provenance audit. No network."""
from pathlib import Path
from collections import Counter
import hashlib,json
import pandas as pd

HERE=Path(__file__).resolve().parent;DATA=Path('/Users/bytedance/repos/my-quant/data')
MQ=Path('/Users/bytedance/repos/my-quant');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
MP=DATA/'processed/security_memberships/security_memberships.parquet'
RAW=DATA/'raw/akshare/membership/security_memberships/20260516T073635Z_membership_sw_industry_clf_hist_a1.parquet'
TAX=DATA/'processed/industry_taxonomy/industry_taxonomy.parquet'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if x is pd.NaT or x is pd.NA:return None
    if isinstance(x,pd.Timestamp):return str(x.date())
    if hasattr(x,'item'):return clean(x.item())
    return x
def records(x):return clean(x.to_dict('records'))
def main():
    m=pd.read_parquet(MP).sort_values(['symbol','effective_start_date']).reset_index(drop=True);raw=pd.read_parquet(RAW);tax=pd.read_parquet(TAX)
    assert len(m)==len(raw)==12780 and m.symbol.nunique()==5862
    k=raw.copy();k['code']=k.symbol.astype(str).str.zfill(6);k['start']=pd.to_datetime(k.effective_start_date);k['cat']=k.category_code.astype(str);k['update']=pd.to_datetime(k.update_time)
    a=m.copy();a['code']=a.symbol.str.split('.').str[0];a['start']=a.effective_start_date;a['cat']=a.category_code.astype(str)
    j=a.merge(k[['code','start','cat','update']],on=['code','start','cat'],how='outer',validate='one_to_one',indicator=True)
    assert j['_merge'].eq('both').all()and j.known_from.eq(j['update']).all()and j.snapshot_date.eq(j['update']).all()
    assert m.effective_end_date.isna().all()
    prev=m.groupby('symbol').category_code.shift();nxt=m.groupby('symbol').effective_start_date.shift(-1)
    assert not (m.groupby(['symbol','effective_start_date']).category_code.nunique()>1).any()
    examples=[]
    for sid in ['000001.SZ','000620.SZ','002583.SZ','300085.SZ','600000.SH','600019.SH']:
        z=m[m.symbol==sid][['symbol','category_code','effective_start_date','known_from']].copy()
        z['derived_end_exclusive_not_source']=nxt.loc[z.index]
        examples.extend(records(z))
    bars_path=HERE.parent/'bars/BAR_SYMBOL_COVERAGE.csv';bars=pd.read_csv(bars_path,dtype={'symbol':str})
    matched=set(bars.symbol)&set(m.symbol);missing=set(bars.symbol)-set(m.symbol)
    first=m.groupby('symbol').effective_start_date.min();bj=bars.join(first,on='symbol');bj['pre_first_gap_days']=(bj.effective_start_date-pd.to_datetime(bj['first'])).dt.days
    firstgaps=bj[bj.pre_first_gap_days>0]
    bcoverage={}
    for date in ['2005-01-01','2022-01-04','2023-01-03','2024-01-02','2025-07-01','2026-05-15']:
        active=bars[(bars['first']<=date)&(bars['last']>=date)]
        h=m[m.effective_start_date<=date].groupby('symbol').tail(1)
        bcoverage[date]=dict(bar_first_last_envelope_symbols=len(active),retrospective_classification_available=len(set(active.symbol)&set(h.symbol)),meaning='Envelope only, not exact-day tradability/listing/known-at-PIT proof')
    selpath=RR/'a-share-selection-e0-20261024/inputs-v2/selection.json';sel=json.loads(selpath.read_text());qualified=[r for r in sel['lines']if r['company_cap_cny']is not None]
    ids={r['security_id']for r in qualified};sectors={r['sector_id']for r in qualified};ths=set(tax[tax.source_interface=='stock_board_industry_name_ths'].category_code)
    pull=DATA/'meta/pulls/akshare/membership/security_memberships/20260516T073635Z_membership_sw_industry_clf_hist_a1.json';pm=json.loads(pull.read_text())
    ta_base=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/results/ths-industry-snapshot')
    ta_rows=json.loads((ta_base/'memberships.json').read_text());assert all(r['effective_from']is None and r['effective_to']is None for r in ta_rows)
    currentmaster=RR/'current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv';cm=pd.read_csv(currentmaster,dtype=str,keep_default_na=False)
    result=dict(status='PASS_BOUNDED_LOCAL_HISTORICAL_CLASSIFICATION_AND_PIT_SEMANTICS_REVIEW',
        verdict=dict(genuine_retrospective_SW_change_history_present=True,successor_start_half_open_proxy_feasible=True,source_end_intervals_provided=False,historical_first_publication_PIT_certified=False,SW_members_not_THS_index_members=True),
        memberships=dict(rows=len(m),symbols=m.symbol.nunique(),category_codes=m.category_code.nunique(),taxonomy='sw',provider='akshare',source_interface='stock_industry_clf_hist_sw',
            effective_start_min=m.effective_start_date.min(),effective_start_max=m.effective_start_date.max(),effective_start_unique=m.effective_start_date.nunique(),effective_start_missing=int(m.effective_start_date.isna().sum()),effective_end_missing=int(m.effective_end_date.isna().sum()),
            rows_per_symbol_distribution=m.groupby('symbol').size().value_counts().sort_index().to_dict(),multi_record_symbols=int((m.groupby('symbol').size()>1).sum()),
            chronological_code_change_rows=int((prev.notna()&m.category_code.ne(prev)).sum()),consecutive_unchanged_code_rows=int((prev.notna()&m.category_code.eq(prev)).sum()),
            same_symbol_start_multicode_groups=int((m.groupby(['symbol','effective_start_date']).category_code.nunique()>1).sum()),duplicate_symbol_start_code_rows=int(m.duplicated(['symbol','effective_start_date','category_code']).sum()),
            repeated_symbol_code_at_different_starts=int(m.duplicated(['symbol','category_code']).sum()),
            same_symbol_update_date_multicode_groups=int((m.groupby(['symbol','known_from']).category_code.nunique()>1).sum()),
            code_level=dict(explicit_level_column=False,all_codes_end_non00=True,rows_ending00=int(m.category_code.str.endswith('00').sum()),local_SW_level_dictionary_found_in_selected_taxonomy=False,interpretation='Do not assert mixed level1/2/3 simultaneously explains these histories; endpoint is one classification-code column. Exact level not independently certified.'),
            known_from_equals_raw_update_all_rows=True,known_after_effective_start=int((m.known_from>m.effective_start_date).sum()),known_before_effective_start=int((m.known_from<m.effective_start_date).sum()),
            raw_start_to_processed_one_to_one_exact=True,start_dates_filled_by_local_cleaner_in_this_data=0,is_current_column_present=False,
            known_from_created_from_snapshot_update_rows=len(m),category_name_fallback_equals_code_rows=int(m.category_name.eq(m.category_code).sum())),
        source_times=dict(recorded_pull_at=pm['pulled_at'],requested_range=pm['requested_range'],processed_created_at=json.loads((DATA/'meta/runs/security_memberships_20260516T073635Z_security_memberships.json').read_text())['created_at'],
            observed_at_values=[str(v.date())for v in sorted(m.observed_at.unique())],observed_at_meaning='Builder config.end=2026-05-15, not actual fetch receipt',
            known_from_min=m.known_from.min(),known_from_max=m.known_from.max(),known_from_source='raw update_time via snapshot_date default; not verified first publication',
            pit_labels='effective_dated andlookahead_riskFalse hardcoded by builder, not independent PIT evidence',source_HTTP_or_original_XLS_vintage_retained_in_this_pull_manifest=False,producer_AKShare_package_version_recorded_in_pull_manifest=False),
        retrospective_proxy=dict(derived_closed_intervals=int(nxt.notna().sum()),derived_open_terminal_rows=int(nxt.isna().sum()),internal_gaps_if_using_successor='Zero by construction, not source-certified zero gaps',true_internal_unclassified_gap_count='UNKNOWN: no source end dates',terminal_rows_are_source_is_current=False,real_examples=examples),
        year2005=dict(effective_from_column_present=False,effective_start_2005_01_01_rows=records(m[m.effective_start_date.eq('2005-01-01')][['symbol','category_code','effective_start_date','known_from']]),local_all_table_2005_backfill=False,meaning='000759.SZ one raw-returned计入日期, not universal initialization. Raw provider historical truth/publication vintage not independently certified; no other unspecified effective_from2005 table audited.'),
        taxonomy=dict(rows=len(tax),THS_industries=int((tax.source_interface=='stock_board_industry_name_ths').sum()),THS_concepts=int((tax.source_interface=='stock_board_concept_name_ths').sum()),SW_to_local_THS_code_intersection=len(set(m.category_code)&set(tax.category_code)),SW_names_or_parent_level_bridge_available=False),
        bars_exact_symbol_coverage=dict(bar_symbols=len(bars),mapped_SW_symbols=len(matched),unmapped_symbols=len(missing),unmapped_exchange_counts=dict(Counter(s.rsplit('.',1)[-1]for s in missing)),
            SW_legacy_BJ_symbols=sorted(m[m.symbol.str.endswith('.BJ')].symbol.unique()),aliases_or_issuer_bridge_applied=False,
            mapped_bar_first_before_first_SW_start_symbols=len(firstgaps),pre_first_gap_examples=records(firstgaps.sort_values('pre_first_gap_days',ascending=False).head(6)),
            caveat='Exact-symbol gaps may reflect ticker/issuer histories, not proof company had no classification; not backfilled.',envelope_samples=bcoverage),
        TradingAlarm=dict(actual_current_master_rows=len(cm),current_master_unique_symbols=cm.current_symbol.nunique(),selection_rows=len(sel['lines']),qualified1709=len(qualified),qualified_industries=len(sectors),
            roster_asof=sel['roster_asof'],cap_observed_date=sel['cap_observed_date'],selection_observed_at=sel['observed_at'],market_timestamp_unknown=sel['market_timestamp_unknown'],
            qualified_exact_SW_mapped=len(ids&set(m.symbol)),qualified_SW_unmapped=sorted(ids-set(m.symbol)),THS90_code_overlap=len({s.removeprefix('URFI')for s in sectors}&ths),
            industry_mapping_source='Current22Oct master/Block tree rederived inrepair_classification.py, no historical effective intervals',
            separate_cache_snapshot_rows=len(ta_rows),separate_cache_effective_from_to_all_null=True,separate_cache_observed_at=ta_rows[0]['observed_at'],separate_cache_scope='Observed A/HK cache, not historical mapping; no machinewide absence claim'),
        usable_scope='Retrospective stock-code classification grouping with explicit successor-derived intervals and unknown/alias gaps; not vintage-PIT industry admission and not THS index constituent evidence. No derived full dataset or strategy constructed.',
        remaining_unknowns=['Historical SW code level/name/version bridge not locally certified','Historical first publication or immutable revision vintages unknown','Source membership ends/current flags not supplied','Ticker/issuer alias bridge not performed','Any different unspecified effective_from2005 artifact outside named data not audited'],
        scope_limit='Only named membership/taxonomy/raw/meta, their generation/loader code, original1709current master and one observed THS cache; not whole repo/machine inventory',
        network_calls=0,data_updates=0,new_accounts=0)
    paths=[MP,RAW,TAX,pull,DATA/'meta/runs/security_memberships_20260516T073635Z_security_memberships.json',DATA/'meta/runs/industry_taxonomy_20260516T073635Z_industry_taxonomy.json',bars_path,selpath,RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json',currentmaster,RR/'a-share-selection-e0-20261024/code/repair_classification.py',MQ/'src/my_quant/data/builders/a_share_boards/builder.py',MQ/'src/my_quant/data/cleaning.py',MQ/'src/my_quant/data/loader.py',MQ/'src/my_quant/data/sources/__init__.py',ta_base/'memberships.json',ta_base/'review.json',Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/ths_industry_snapshot.py'),Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/lib/python3.13/site-packages/akshare/stock/stock_industry_sw.py'),Path(__file__)]
    result['source_sha256']={str(p.resolve()):sha(p)for p in paths}
    HERE.mkdir(parents=True,exist_ok=True);out=HERE/'EVIDENCE.json';out.write_text(json.dumps(clean(result),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(clean({k:result[k]for k in ['status','verdict','bars_exact_symbol_coverage']}) ,ensure_ascii=False)[:2400]);print('EVIDENCE_SHA',sha(out))

if __name__=='__main__':main()
