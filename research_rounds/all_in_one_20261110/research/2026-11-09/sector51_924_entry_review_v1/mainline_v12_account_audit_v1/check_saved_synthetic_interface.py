"""Validate builder's saved synthetic fixture without importing candidate or Data."""
from pathlib import Path
import json,sys
sys.dont_write_bytecode=True
import accounting_core as au
import verify_saved_funding_semantics as sem
O=Path(__file__).resolve().parent;R=O.parent
def main():
    p=R/'mainline_candidate_v12_winner_funding_competition/synthetic_fixture';m=au.read(p/'FIXTURE_MANIFEST.json')
    assert m['synthetic_only'] is True and m['history_run'] is False and m['real_Data_constructed'] is False
    for n,h in m['files'].items():assert au.sha(p/n)==h
    books=au.read(p/'FUNDING_BRANCH_BOOKS.json');ds=au.read(p/'FUNDING_OPEN_DECISIONS.json');aa=au.read(p/'FUNDING_ACTUAL_DIAGNOSTICS.json');wait=au.read(p/'FUNDING_WAIT_LOG.json')
    count=0;summary=[]
    for book,d,a in zip(books,ds,aa):
        assert sem.digest({k:v for k,v in book.items() if k!='book_id'})==book['book_id'];count+=1
        ids={sem.request_id(r):r for r in book['original_requests']};assert len(ids)==len(book['original_requests'])
        assert set(book['A'])=={k for k,r in ids.items() if sem.protected(r)}
        assert set(book['N_priority'])=={k for k,r in ids.items() if sem.new_seed(r)};count+=1
        shadow=book['branches'][-1];passing=[]
        for i,b in enumerate(book['branches']):
            assert b['retained']==book['N_priority'][:len(book['N_priority'])-i]
            assert b['branch_id']==sem.digest({k:b[k] for k in ('retained','requests','plan','event_reserved','bar_q_C')});count+=1
            sem.reference(b);count+=1
            sem.quantities(b['close_projection'],b,ids);count+=1
            c=sem.comparison(b['close_projection'],shadow['close_projection'],book['H'],book['A']);sem.equivalent_comparison(b['close_comparison'],c);count+=1
            if c['passed']:passing.append(i)
        assert book['selected_close_index']==passing[0];count+=1
        assert d['book_id']==book['book_id'] and d['selected_index']==1
        assert d['health_snapshot_id']==sem.digest([d['day'],'OPEN',d['common_conditional_prefix'],d['H']]);count+=1
        assert d['chosen_projection']==d['shadow_projection'];count+=1
        for e in d['evaluated']:
            b=book['branches'][e['index']];sem.quantities(e['projection'],b,ids);sem.equivalent_comparison(e['comparison'],sem.comparison(e['projection'],d['shadow_projection'],d['H'],book['A']));count+=1
        assert a['actual_q']==d['chosen_projection']['q'] and a['actual_y']==d['chosen_projection']['y'] and a['reselected'] is False;count+=1
        adds=[r for r in a['actual_orders'] if r['side']=='BUY_ADD'];assert len(adds)==1 and adds[0]['qty']==300
        assert len(wait)==1 and wait[0]['actual_quantity']==0 and not wait[0]['new_round_created'] and wait[0]['reason']=='FUNDING_NONDISPLACEMENT_WAIT';count+=1
        row=dict(full_CLOSE_q=book['branches'][0]['close_projection']['q'],shadow_CLOSE_q=shadow['close_projection']['q'],selected_index=d['selected_index'],actual_q=a['actual_q'],wait_request=wait[0]['request_id']);summary.append(row)
    result=dict(verdict='PASS_SAVED_SYNTHETIC_INTERFACE',assertion_groups=count,fixture_manifest_sha256=au.sha(p/'FIXTURE_MANIFEST.json'),fixture_engine_sha256=m['engine_sha256'],fixture_tests_sha256=m['tests_sha256'],summary=summary,scope='Independent pure-JSON content-hash/identity/branch-reference/q/y decoding of artificial fixture. Not actual historical account accounting or raw-source timing proof.',strategy_imported=False,history_executed=False,auditor_source_sha256=au.sha(__file__),semantic_checker_sha256=au.sha(sem.__file__))
    au.save('SYNTHETIC_INTERFACE_AUDIT',result);print(json.dumps(result,ensure_ascii=False,default=str))
if __name__=='__main__':main()
