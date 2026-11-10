"""Bounded saved-output/source review; never imports or runs signal models."""
from pathlib import Path
import json,hashlib,csv
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
E=BASE/'eligibility_source/fixed35';G=BASE/'universe_gate_data'
L=BASE.parent/'local_observable_selection_v1'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    bindings={}; checks=0
    for folder,filename,key in [(E,'SEAL.json','files'),(G,'DELIVERABLE_SHA256.json','sha256')]:
        manifest=load(folder/filename);bindings[str((folder/filename).resolve())]=sha(folder/filename)
        for name,h in manifest[key].items():
            p=folder/name if folder==E else Path(name)
            assert sha(p)==h,(str(p),'seal');checks+=1
    sample=load(E/'SAMPLE_FREEZE.json');freeze=load(BASE/'FIXED35_FREEZE.json')
    for p,h in sample['source_sha256'].items(): assert sha(p)==h;checks+=1
    for p,h in sample['algorithm_code_sha256'].items(): assert sha(p)==h;checks+=1
    # Re-form the frozen sample using prior saved rank lists, not model outputs.
    lists=pd.read_csv(L/'ranks/ALL_TOP20_LISTS.csv')
    lists=lists[lists.day.eq('2024-09-24')&lists.queue.eq('PVR')]
    assert len(lists)==40 and lists.scope.value_counts().eq(20).all()
    ids=set(lists.sid);assert len(ids)==35 and ids==set(sample['symbols'])==set(freeze['sample_ids'])
    x=pd.read_parquet(E/'FIXED35_2024_09_24.parquet')
    assert len(x)==35 and x.sid.nunique()==35 and set(x.sid)==ids and x.day.eq('2024-09-24').all()
    assert x.S0_eligibility_q.isna().all()
    assert set(x.S0_status)=={'NOT_EVALUATED_STOCK_ONLY_NO_CAP_SECTOR_OR_MARKET_GATE','NOT_EVALUATED_STOCK_ONLY_NO_INVENTED_CAP_SECTOR_OR_MARKET_FACTS'}
    assert set(x.loc[x.S0_status.eq('NOT_EVALUATED_STOCK_ONLY_NO_INVENTED_CAP_SECTOR_OR_MARKET_FACTS'),'sid'])==set(sample['reused_symbols'])
    features=pd.read_parquet(L/'features/LOCAL_FIXED_DATE_FEATURES.parquet')
    f=features[features.day.eq('2024-09-24')&features.sid.isin(ids)].set_index('sid').sort_index()
    xx=x.set_index('sid').sort_index()
    for col in ['score','E','e','E_fast','E_slow','raw_close','current_close_qfq','current_amount_passthrough']:
        a=xx[col].to_numpy(float);b=f[col].to_numpy(float)
        assert np.array_equal(a.view(np.uint64),b.view(np.uint64)),col
    assert np.array_equal(xx.close.to_numpy(float).view(np.uint64),f.current_close_qfq.to_numpy(float).view(np.uint64))
    assert x.e0_ready.eq(1).all()
    hold=x.i_target.eq(1);fresh=hold & x.i_buy.eq(True)
    assert np.array_equal(hold,x.stock_hold_signal) and np.array_equal(fresh,x.stock_fresh_core_signal)
    opportunity=x.e0_target.eq(1)&x.g_ready.eq(True)&x.g_grade.ge(2)&(x.e0_entered.eq(1)|x.g_fresh_up.eq(True))
    assert np.array_equal(x.i_buy.eq(True),x.i_target.eq(1)&opportunity)
    assert int(hold.sum())==34 and int(fresh.sum())==32
    assert list(x.sort_values(['score','sid'],ascending=[False,True]).fixed35_bare_PVR_rank)==list(range(1,36))
    for label,mask in [('hold',hold),('fresh',fresh)]:
        z=x.loc[mask].sort_values(['score','sid'],ascending=[False,True])
        assert list(z['fixed35_'+label+'_PVR_rank'])==list(range(1,len(z)+1))
    scope_summary={}
    for scope,gg in lists.groupby('scope'):
        z=x[x.sid.isin(gg.sid)];assert z[scope+'_top20_member'].all()
        scope_summary[scope]={'members':len(z),'hold':int(z.stock_hold_signal.sum()),'fresh':int(z.stock_fresh_core_signal.sum())}
    assert scope_summary=={'FULL_LOCAL':{'members':20,'hold':20,'fresh':19},'OLD1709_EXACT_SUBPOOL':{'members':20,'hold':19,'fresh':17}}
    cases=x[~x.stock_fresh_core_signal][['sid','e0_ready','e0_target','e0_entered','i_target','i_buy','g_grade','g_ready','g_fresh_up','numeric_event']].to_dict('records')
    assert {r['sid']for r in cases}=={'600550.SH','600268.SH','600675.SH'}
    assert set(x.loc[x.reused_stopped_partial,'sid'])=={'600292.SH','600718.SH'}
    # Compare the two reused records with their saved stopped-batch rows.
    reused={}
    for p in (BASE/'eligibility_source').glob('SHARD_*_STOCK_SIGNAL.jsonl'):
        for line in p.open():
            r=json.loads(line)
            if r['sid']in sample['reused_symbols']:reused[r['sid']]=r
    for sid,r in reused.items():
        row=xx.loc[sid]
        for c in ['close','e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_ready','g_fresh_up','numeric_event']:
            assert row[c]==r[c],(sid,c,'reused')
    cap=load(G/'CANONICAL5517_MAP_CAP_DATA_AVAILABILITY.json')
    assert len(cap)==5517 and len({r['symbol']for r in cap})==5517
    allcap=pd.DataFrame(cap);outside=allcap[~allcap.in_old1709]
    assert len(outside)==3836
    assert outside.current_cap_status.value_counts().to_dict()=={'CURRENT_CAP_NOT_GT10BN':3817,'NOT_IN_CURRENT_ROSTER':17,'CURRENT_CAP_UNKNOWN':2}
    assert outside.current_THS_sector.notna().sum()==3818 and outside.sector_existing_prepared.sum()==3818
    assert allcap.current_THS_sector.notna().sum()==5499
    # Read the original saved roster/map and independently join all35 rows.
    gr=load(G/'AUDIT_RECEIPT.json')
    rosterpath=next(Path(p)for p in gr['source_sha256']if p.endswith('roster-dispositions.json'))
    mappath=next(Path(p)for p in gr['source_sha256']if p.endswith('current-stock-master.industry-resolved.csv'))
    for p in [rosterpath,mappath]:assert sha(p)==gr['source_sha256'][str(p)];bindings[str(p)]=sha(p)
    roster={r['symbol']:r for r in load(rosterpath)}
    with mappath.open()as f:rawmap={r['symbol']:r for r in csv.DictReader(f)}
    sectors=load(G/'ALL90_THS_SECTOR_FIXED_DAY_SOURCE_ROWS.json');assert len(sectors)==90
    sectorrows={r['sector_id']:r for r in sectors}
    cdict={r['symbol']:r for r in cap};joined=[]
    for sid in sorted(ids):
        c=cdict[sid];rr=roster[sid];mm=rawmap[sid]
        assert c['current_cap_cny']==rr['cap_cny'] and c['cap_observed_at']==rr['cap_observed_at']
        assert c['current_THS_sector']==mm['industry_index_symbol']
        knownpass=c['current_cap_cny'] is not None and c['current_cap_cny']>10_000_000_000
        assert knownpass==(c['current_cap_status']=='CURRENT_CAP_GT10BN')
        sr=sectorrows[c['current_THS_sector']]['data']['native_E0_sector_facts']['row']
        row=xx.loc[sid]
        joined.append({'sid':sid,'stock_hold_signal':bool(row.stock_hold_signal),'stock_fresh_core_signal':bool(row.stock_fresh_core_signal),'in_old1709':c['in_old1709'],'current_cap_cny':c['current_cap_cny'],'current_cap_gt10bn':knownpass,'cap_observed_at':c['cap_observed_at'],'current_THS_sector':c['current_THS_sector'],'sector_native_e0_ready':sr['e0_ready'],'sector_native_e0_target':sr['e0_target'],'full_S0':'NOT_EVALUATED'})
    outside35=[r for r in joined if not r['in_old1709']]
    assert len(outside35)==15 and all(r['stock_hold_signal']and r['stock_fresh_core_signal']for r in outside35)
    assert not any(r['current_cap_gt10bn']for r in outside35)
    # Verify the small original sector rows for the three failure examples plus one outside example.
    spotids=sorted({cdict[s]['current_THS_sector']for s in ['600550.SH','600268.SH','600675.SH','600198.SH']})
    for sid in spotids:
        r=sectorrows[sid];ff=r['files']['native_E0_sector_facts'];p=Path(ff['path']);assert sha(p)==ff['sha256']
        q=pd.read_parquet(p).loc[pd.Timestamp('2024-09-24')]
        for c in ['close','e0_ready','e0_target','e0_floor']:assert float(q[c])==float(r['data']['native_E0_sector_facts']['row'][c])
        bindings[str(p)]=sha(p)
    pd.DataFrame(joined).to_csv(OUT/'FIXED35_COMPONENT_GATE_JOIN.csv',index=False)
    original_sources=[Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py')]
    for p in original_sources+[BASE/'FIXED35_FREEZE.json',E/'SAMPLE_FREEZE.json',E/'COMPLETION.json',BASE/'eligibility_source/stock_signal.py',Path(__file__)]:bindings[str(p.resolve())]=sha(p)
    result={'status':'PASS_BOUNDED_FIXED35_STOCK_SIGNAL_AND_SNAPSHOT_NECESSARY_GATES_WITH_LIMITS','remaining_execution_blocks':[],'hash_checks':checks,'source_static_findings':{'cache':'cache.py23-28 fixes decline_candidate=False and projects G1_I. Wrapper independently regenerates original numeric/participation/evidence/classify on canonical input instead of transplanting old cached targets.','project':'policies_g1.py16-34: warm grade>=2 plus entered/fresh is entry opportunity; G1_I holding is maintained by E0 shadow/old floor, not daily warm.','cap':'active sector_stock_admission.py201-219: cap>10bn remains necessary, stock/sector ranks freshness, sector state, common readiness and buy_allowed remain separate. Unknown retained even when a known gate fails.'},'fixed_sample':{'rows':35,'raw_list_rows':40,'overlap':5,'reused':2,'new_original_function_rows':33,'ready':35,'hold':34,'fresh':32,'by_original_scope':scope_summary,'outside_old_top15_hold':15,'outside_old_top15_fresh':15,'outside_old_top15_current_cap_pass':0},'no_fresh_cases':cases,'outside_old_snapshot_cap':{'rows':3836,'known_pass':0,'known_fail':3817,'unknown_cap':2,'not_in_current_roster':17},'bitexact_saved_fields':['close versus canonical current_close_qfq','score','E','e','E_fast','E_slow','raw_close','current_close_qfq','current_amount_passthrough'],'sector_original_spotchecks':spotids,'limits':['Saved35 state fields and current predicates checked; complete E0/I recursive state not independently rerun. Original function sources bound/static-read; no new model execution.','32fresh/34hold/15outside fresh do not mean full S0 pass or globally qualified top20. Stock fresh is not an independent new structure guarantee.','i_buyFalse does not forbid all original MOBILE: continuing eligibility can replace daily buy_allowed with market_buyable while other gates and freshCP remain. Same-source CP,H1 and market eligibility not computed here.','Current cap and THS map are2026 snapshots; outside knownpass0 is a preserved snapshot research necessary-gate fact, not2024 actual historical all-market qualification.','Only35 frozen list-union examples; not a complete5517 signal-qualified universe. Current native sector E0 fields are not full S0 or sector G1/I.','No accounts, price/indicator recalculation, source refresh, future labels or parameter search in this review.'], 'bindings':bindings,'component_csv_sha256':sha(OUT/'FIXED35_COMPONENT_GATE_JOIN.csv')}
    result['audit_technical_note']='First read-only audit stopped on overly narrow S0_status text equality: the two reused rows retain prior NOT_EVALUATED_STOCK_ONLY_NO_INVENTED_CAP_SECTOR_OR_MARKET_FACTS wording;33 new rows use NOT_EVALUATED_STOCK_ONLY_NO_CAP_SECTOR_OR_MARKET_GATE. Both have S0_eligibility_q=None. Assertion now checks the exact two texts and their exact reuse partition; no producer/model/data changed.'
    p=OUT/'FIXED35_FINAL_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(p),'fixed_sample':result['fixed_sample'],'sector_spotcheck_count':len(spotids)},ensure_ascii=False))
if __name__=='__main__':main()
