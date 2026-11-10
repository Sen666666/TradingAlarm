"""Read old sealed output only. No real Data, history replay, or input modification."""
from pathlib import Path
import importlib.util,json,sys
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('prefix_prep_engine',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
c=e.module('prefix_reference_rules',P/'prefix_check.py')
parser_path=P.parent/'mainline_v12_account_audit_v1/stream_branch_books.py'
assert e.stream.file_sha(parser_path)=='0dd79a9335a12dc948a19295129e2268a6aa0615efb0bab17c4bc898dcc770e0'
p=e.module('sealed_branch_stream_parser',parser_path)
def main():
    inventory=json.loads((c.BASE/'OUTPUT_HASHES.json').read_text());sources={str(c.BASE/'OUTPUT_HASHES.json'):e.stream.file_sha(c.BASE/'OUTPUT_HASHES.json'),str(parser_path):e.stream.file_sha(parser_path)}
    def read(name):
        path=c.BASE/(name+'.json');h=e.stream.file_sha(path);assert h==inventory[path.name],('BASELINE_DRIFT',name);sources[str(path)]=h
        return json.loads(path.read_text())
    raw={name:read(name) for name in c.DAILY};days=[r['day'] for r in raw['DAY_LEDGER']]
    assert len(days)==22 and days[-1]=='2024-10-10'
    byday={day:dict(day=day,daily_hashes={n:c.digest([r for r in rows if r['day']==day]) for n,rows in raw.items()}) for day in days}
    final={n:c.digest(read(n)) for n in [*c.FINAL,'PENDING_AT_END','ATTEMPTS']}
    path=c.BASE/'FUNDING_BRANCH_BOOKS.json';h=e.stream.file_sha(path);assert h==inventory[path.name];sources[str(path)]=h
    count=0
    for book in p.iter_books(path,lambda b,i,meta,ctx:c.stream_hash(b,e.stream)):
        descriptor=c.book_descriptor(book,book['branches']);byday[book['close_day']]['book_descriptor_sha256']=c.digest(descriptor);count+=1
        print('REFERENCE_BOOK '+book['close_day'],flush=True)
    assert count==22
    result=dict(result='SEALED_V1_CERTIFIED_22_DAY_REFERENCE',history_run=False,real_Data_constructed=False,days=[byday[d] for d in days],final_state_hashes=final,source_hashes=sources,
      exact_allowed_difference={'2024-10-10':{'native_snapshot':{'sid':'688200.SH','record_date':'2024-10-10','q':0,'round':None},'book_fields':['book_id','scratch_integrity.before','scratch_integrity.after']}},
      equity_events_excluded=False,branches_fully_hashed=True,output_only_exclusions=['SOURCE_HASHES','EVENT_ADMISSION','OUTPUT_HASHES','BLOCKERS','UNCERTIFIED_DAY','ALL_TARGETS_BLOCKER_SCAN'])
    with (P/'PREFIX_REFERENCE.json').open('x') as out:json.dump(result,out,ensure_ascii=False,indent=2);out.write('\n')
    print('PREFIX_REFERENCE_READY '+e.stream.file_sha(P/'PREFIX_REFERENCE.json'),flush=True)
if __name__=='__main__':main()
