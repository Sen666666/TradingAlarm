"""Read-only original-source inventory and earliest-event fixture freezing."""
from pathlib import Path
import json,hashlib,ast
import pandas as pd
from bridge import ROOT,EVENT_ROOT as E,HERE,ENGINES,sha
def save(name,value):
    with (HERE/name).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,default=str);f.write('\n')
def main():
    paths=[E/'PROTOCOL.json',E/'freeze_events.py',E/'SEALED_ALL_BIRTH_EVENTS.csv',E/'EVENT_SEAL.json',
           E/'relative_priority_v1/simulate.py',E/'relative_priority_v1/priority.py',E/'relative_priority_v1/PROTOCOL.json',
           E/'relative_priority_v1/FREEZE.json',ROOT/'unified_probe_account_contract_v1/unified_probe.py',
           E/'relative_m3_cache_v1/coverage_upper_bound_v1/EVENT_COVERAGE.csv',
           ROOT/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet']
    names=('ROUNDS','ACTIONS','DECISIONS','RANKING_AUDIT','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES')
    for directory,baseline in ENGINES.values():
        paths += [E/directory/'engine.py',E/directory/'run.py',E/directory/'READOUT.md',E/directory/baseline/'OUTPUT_HASHES.json']
        paths += [E/directory/baseline/(name+'.csv') for name in names]
    paths += [E/'relative_priority_v1/baseline'/f for f in ('ACTIONS.csv','DECISIONS.csv')]
    digests={str(p):sha(p) for p in paths}
    definitions={}
    for p in paths:
        if p.suffix!='.py':continue
        source=p.read_text();rows={}
        for node in ast.parse(source).body:
            if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
                rows[node.name]={'line_start':node.lineno,'line_end':node.end_lineno,'sha256':hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()}
        definitions[str(p)]=rows
    save('SOURCE_MANIFEST.json',{'status':'INDEPENDENTLY_READ_AND_HASHED_ON_MAC','sha256':digests,'definition_map':definitions,
         'source_effects':'simulate and freeze_events have executable top-level writes, never imported; equity engines are explicit read/setup loads, replay only by named API',
         'shared_economic_run':False,'source_data_non_pit':True})
    e=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',low_memory=False)
    panel=pd.read_parquet(paths[10],columns=['sector','day','M3_candidate']).sort_values(['sector','day'])
    jan4=e[e.day.eq('2022-01-04')]
    assert panel.day.min()==pd.Timestamp('2022-01-04') and panel.groupby('sector').first().day.eq(pd.Timestamp('2022-01-04')).all()
    assert len(jan4)==344 and jan4.event_type.eq('OTHER_UNKNOWN_OR_LEFT').all() and jan4.previous_sector_state.isna().all()
    fixtures=[]
    for window,directory,baseline in [('2022',*ENGINES['2022']),('2024_924',*ENGINES['2024_924']),('2026H1_SEMI','relative_priority_v1','baseline')]:
        d=pd.read_csv(E/directory/baseline/'DECISIONS.csv',low_memory=False);d=d[d.arm.eq('A_UNION_B')&d.window.astype(str).eq(window)]
        a=pd.read_csv(E/directory/baseline/'ACTIONS.csv',low_memory=False);a=a[a.arm.eq('A_UNION_B')&a.window.astype(str).eq(window)]
        legal=e[e.window.astype(str).eq(window)&e.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
        signal=legal.day.min();selected_day=d[d.selected.eq(True)].day.min();first_open=a[a.side.eq('buy_core')].day.min()
        assert signal==selected_day
        selected=d[d.day.eq(signal)&d.selected.eq(True)]
        first=a[a.day.eq(first_open)&a.side.eq('buy_core')]
        assert len(selected)>0 and len(first)>0
        fixture={'window':window,'first_legal_signal':signal,'first_selected_signal':selected_day,'first_execution_open':first_open,
                 'first_signal_decisions':len(d[d.day.eq(signal)]),'selected':len(selected),'first_open_fills':len(first),
                 'source_baseline':str(E/directory/baseline),'2026_signal_diagnostic_only':window=='2026H1_SEMI'}
        fixtures.append(fixture)
        dest=HERE/('fixture_'+window);dest.mkdir(exist_ok=False)
        for name,frame in [('EVENTS',legal[legal.day.eq(signal)]),('DECISIONS',d[d.day.eq(signal)]),('FIRST_OPEN_ACTIONS',a[a.day.eq(first_open)])]:
            with (dest/(name+'.csv')).open('x') as f:frame.to_csv(f,index=False)
    save('NONEMPTY_FIXTURE_SEAL.json',{'jan4_initialization':{'panel_sectors':90,'observations':344,'legal_ab':0,'all_previous_sector_unknown':True},
         'fixtures':fixtures,'method':'existing sealed signals and baseline first events, no forward winner selection','no_input_state_rewritten':True,
         'fixture_hashes':{str(p.relative_to(HERE)):sha(p) for p in HERE.glob('fixture_*/*.csv')}})
    print(json.dumps({'source_files':len(digests),'fixtures':fixtures},ensure_ascii=False))
if __name__=='__main__':main()
