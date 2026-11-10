"""Read-only exact prior-rule census. No account or signal recomputation."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,hashlib,json,time
import pandas as pd

O=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/trend-reentry-20261027')
MONEY=OLD.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def csvrows(p):return list(csv.DictReader(Path(p).open()))

def main():
    t=time.monotonic();inp=read(OLD/'input.json');freeze=read(OLD/'freeze.json')
    coverage=csvrows(OLD/'coverage.csv');additional=csvrows(OLD/'additional-events.csv')
    funnel=csvrows(OLD/'event-funnel.csv');resources=csvrows(OLD/'resource-diagnosis.csv')
    totals=defaultdict(Counter)
    for r in coverage:
        totals[r['version']]['events']+=int(r['events'])
        totals[r['version']]['additional_no_i_buy']+=int(r['additional'])
    # Verify the saved PB/BOX i_target labels against the exact old frozen facts.
    cache={};checks=[];sources={}
    for r in additional:
        sid=r['symbol'];p=Path(inp['snapshot'])/'facts'/f'{sid}.parquet'
        if sid not in cache:
            assert sha(p)==inp['source_hashes'][sid]['fact']
            cache[sid]=pd.read_parquet(p,columns=['e0_target','i_target','i_buy'])
            sources[str(p)]=sha(p)
        z=cache[sid].loc[r['date']]
        assert bool(z.e0_target) and not bool(z.i_buy)
        assert str(bool(z.i_target))==r['i_target']
        checks.append(dict(version=r['version'],sid=sid,day=r['date'],E0=True,
                           I_target=bool(z.i_target),i_buy=False))
    both_labels=Counter()
    for r in funnel:
        if r['version']!='BOTH' or r['scenario']!='base':continue
        sid=r['symbol'];p=Path(inp['snapshot'])/'facts'/f'{sid}.parquet'
        if sid not in cache:
            assert sha(p)==inp['source_hashes'][sid]['fact']
            cache[sid]=pd.read_parquet(p,columns=['e0_target','i_target','i_buy']);sources[str(p)]=sha(p)
        z=cache[sid].loc[r['date']]
        assert bool(z.e0_target) and not bool(z.i_buy)
        both_labels[str(bool(z.i_target))]+=1
    fn=defaultdict(Counter);rs=defaultdict(Counter)
    for r in funnel:fn[r['version']+'|'+r['scenario']][r['reason']]+=1
    for r in resources:rs[r['version']][r['resource_state']]+=1
    files=[OLD/'protocol.json',OLD/'code/model.py',OLD/'code/study.py',OLD/'code/finish.py',
           OLD/'CONCLUSION.txt',OLD/'coverage.csv',OLD/'additional-events.csv',OLD/'event-funnel.csv',
           OLD/'resource-diagnosis.csv',OLD/'local-contribution.csv',OLD/'full-verification.json',OLD/'input.json',
           MONEY/'actual-risk-recovery-20261027/code/engine.py',
           MONEY/'actual-risk-recovery-20261027/code/risk_policy.py',
           MONEY/'rs-h1-execution-20261025/code/sector_stock_admission.py']
    for p in files:sources[str(p)]=sha(p)
    code_guards={str(p):dict(current=sha(p),old_frozen=freeze['sources'].get(str(p)),
                exact=sha(p)==freeze['sources'][str(p)])for p in files if str(p)in freeze['sources']}
    assert all(x['exact']for x in code_guards.values())
    result=dict(scope='Exact prior TRE-1 record/source census, not new economic calculation',
        prior_domain=dict(stocks=407,sectors=11,start='2024-01-02',end='2026-10-27',
            initial_cash=1000000,stock_slots=6,sector_slots=3,stocks_per_sector=2,
            initial_nominal_fraction=.15,not_same_as_current_1709_No60=True),
        source_model_event_counts={k:dict(v)for k,v in totals.items()},
        saved_PB_BOX_additional=len(additional),verified_additional_i_target_counts=dict(Counter(str(x['I_target'])for x in checks)),
        A_or_A2_i_target_false_additional_events=sum(not x['I_target']for x in checks),
        BOTH_base_added_events_I_target_counts=dict(both_labels),
        labels_verified_against_original_facts=True,distinct_old_fact_files=len(cache),
        funnel_counts={k:dict(v)for k,v in fn.items()},
        unadmitted_resource_state_counts={k:dict(v)for k,v in rs.items()},
        resource_diagnosis_clock='Original CLOSE after decision/capacity allocation; descriptive occupancy, not unique first route rejection',
        source_guards=code_guards,sources_sha256=sources,
        conclusion='TRE changes buy_allowed only and retains packet I trend/S0. Its added PB/BOX mother has I_target true in all 361 saved additional events. It does not test A early-I authorization or survival while I_target false.',
        actual_rule_note='handoff is local/E0 stop bookkeeping; it never sets stock trend true while I is false or bypasses original normal I/ACT exits',
        seconds=time.monotonic()-t,new_accounts=0,new_signals=0,new_fills=0)
    (O/'PRIOR_TRE_EXACT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k not in ['sources_sha256','source_guards']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
