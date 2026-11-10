"""Evidence-only exact 688200 cash admission; frozen M12 economics, gzip audit output.

No historical launcher. Parent must approve and own any single-run wrapper.
"""
from pathlib import Path
import importlib.util
import hashlib
import json
import sys
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
ROOT=O.parent
FROZEN=ROOT/'mainline_candidate_v12_winner_funding_competition'
FROZEN_SHA='2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(FROZEN/'engine.py')==FROZEN_SHA,'FROZEN_M12_DRIFT'
def module(name,path):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp)
    sys.modules[name]=m;sp.loader.exec_module(m);return m
frozen=module('cash688200_frozen_m12',FROZEN/'engine.py')
stream=module('cash688200_stream_output',O/'stream_output.py')
D,dec,pd,day,Blocked=frozen.D,frozen.dec,frozen.pd,frozen.day,frozen.Blocked
read,save=frozen.base.read,frozen.base.save
ADAPTER=ROOT/'october_remaining_cash_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_688200_V1.json'
ADAPTER_SHA='af9b6319597e47ea858c0125bf0e43d31c270da056e06db8d470d76bdc025686'
EXACT=('688200.SH','2024-10-11','688200.SH|LOCAL_DISTRIBUTION_007')
ALLOWED=frozenset([EXACT])
# Identical previously reviewed loader, including source bridge and NET80 metadata.
native_admit_cash=frozen.base.v.b.v6.admit_cash
LOCK=O/'ADMISSION_LOCK.json'
LOCK_SHA='618aec73520bfd7b4ea778cfb7890e8f4b64db6a82e99138b23070e3d6d93b3e'


def validated_event(checked):
    assert sha(LOCK)==LOCK_SHA,'ADMISSION_LOCK_DRIFT_OR_NOT_APPROVED'
    lock=read(LOCK)
    assert lock['status']=='PASS_EXACT_SINGLE_EVENT_FACT_ADMISSION'
    assert tuple(lock['exact_event'])==EXACT and lock['no_other_event_expansion'] is True
    checked(str(LOCK),LOCK_SHA)
    checked(lock['independent_review_path'],lock['independent_review_sha256'])
    checked(lock['independent_review_text_path'],lock['independent_review_text_sha256'])
    assert read(lock['independent_review_path'])['result']=='PASS_EXACT_688200_20241011_LOCAL_RESEARCH_EVENT_ADMISSION'
    assert lock['adapter_path']==str(ADAPTER) and lock['adapter_sha256']==ADAPTER_SHA
    checked(str(ADAPTER),ADAPTER_SHA)
    events=read(ADAPTER);assert len(events)==1
    ev=events[0];validate_exact(ev)
    return ev


def validate_exact(ev):
    assert (ev['sid'],ev['ex_date'],ev['economic_event_id_candidate'])==EXACT,'EXACT_EVENT_SCOPE'
    assert ev['event_type']=='PURE_CASH' and ev['record_date']=='2024-10-10' and ev['pay_date']=='2024-10-11','EXACT_EVENT_DATES'
    assert (ev['d_source'],ev['d_cash'],ev['d_ref'])==('0.23','0.23','0.2297'),'EXACT_CASH_COORDINATES'
    assert ev['factor_old']=='2.234495011354039' and ev['factor_new']=='2.2388548166866773','EXACT_FACTORS'
    return ev


def admit_exact(data,ev,checked):
    validate_exact(ev)
    # Verify the complete approved row, not just its economic tuple.
    assert sha(ADAPTER)==ADAPTER_SHA,'EXACT_ADAPTER_DRIFT'
    assert ev==read(ADAPTER)[0],'EXACT_SOURCE_IDENTITY'
    return native_admit_cash(data,ev,checked,ALLOWED)


class Data(frozen.Data):
    def __init__(self,end='2026-06-30'):
        recorded={}
        def prechecked(p,h):
            assert stream.file_sha(p)==h,('EXACT_CASH_SOURCE_DRIFT',p);recorded[str(p)]=h
        ev=validated_event(prechecked)
        super().__init__(end)
        self.hashes.update(recorded)
        def checked(p,h):
            assert stream.file_sha(p)==h,('EXACT_CASH_SOURCE_DRIFT',p);self.hashes[str(p)]=h
        admit_exact(self,ev,checked)
        for name in ['engine.py','stream_output.py','checkpoint.py','CONTRACT.md','SOURCE_HASHES.json']:
            self.hashes[str(O/name)]=stream.file_sha(O/name)
        self.hashes[str(FROZEN/'engine.py')]=FROZEN_SHA


class Engine(frozen.Engine):
    def export(self,path):
        path=Path(path).resolve();assert path.is_relative_to(O),'CONTINUATION_OUTPUT_ONLY'
        # Same call as frozen M12 super().export, only its old path guard is bypassed.
        frozen.base.Engine.export(self,path)
        compressed=stream.save_gzip(path/'FUNDING_BRANCH_BOOKS.json.gz',self.funding_books)
        for name,value in [('FUNDING_OPEN_DECISIONS',self.funding_decisions),
                ('FUNDING_WAIT_LOG',self.funding_wait_log),('FUNDING_WAIT_STATE',self.funding_waits),
                ('FUNDING_PREFLIGHT',self.funding_preflight),('FUNDING_ACTUAL_DIAGNOSTICS',self.funding_actual)]:
            save(path/(name+'.json'),frozen.clean(value))
        save(path/'COMPRESSED_OUTPUTS.json',dict(schema='LOSSLESS_JSON_GZIP_V1',files=[compressed]))
        save(path/'OUTPUT_HASHES.json',{p.name:stream.file_sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})


def self_check():
    unchanged=[n for n in dir(frozen.Engine) if not n.startswith('__') and callable(getattr(frozen.Engine,n)) and n!='export']
    assert all(getattr(Engine,n) is getattr(frozen.Engine,n) for n in unchanged)
    assert Data.__bases__==(frozen.Data,)
    assert native_admit_cash is frozen.base.v.b.v6.admit_cash
    return dict(result='PASS',history_run=False,real_Data_constructed=False,base_engine_sha256=FROZEN_SHA,
                unchanged_engine_methods=unchanged,changed_engine_methods=['export'],
                new_Data_only_exact_event=list(EXACT),streaming_branch_books_only=True)

if __name__=='__main__':print(json.dumps(self_check()))
