"""New isolated exact-session halt union. Frozen economic engine unchanged."""
from pathlib import Path
import sys,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'known_evidence_union_diagnostic_v1'))
import union_bridge_v1 as U
bridge=U.bridge; ExecutionBridge=U.ExecutionBridge; sha=U.sha; digest=U.digest
blocking_unknowns=U.blocking_unknowns; C=U.C; native=U.native; ARM=U.ARM; HALT=U.HALT
def merge_hashes(*maps):
    out={}
    for mapping in maps:
        for p,h in mapping.items():
            if p in out and out[p]!=h:raise ValueError('Conflicting source hash: '+p)
            out[p]=h
    return out
class AnnualHalts(U.UnionHalts):
    def __init__(self):
        super().__init__()
        path=HERE/'MAY19_HALT_EVIDENCE.json'
        catalog=json.loads(path.read_text())
        rows=catalog['halts']
        assert len(rows)==1 and (rows[0]['sid'],rows[0]['session'],rows[0]['scope'])==('600595.SH','2022-05-19','FULL_DAY')
        assert rows[0]['exact_session_from_official_halt_row'] and not rows[0]['publisher_original_pdf_available']
        extra=U.C.HaltEvidence(rows)
        self.parts=self.parts+(extra,)
        self.rows=self.rows+tuple(extra.rows)
        self.hashes=merge_hashes(self.hashes,extra.hashes,{str(path):sha(path)})
        assert len({(r['sid'],r['session']) for r in self.rows})==3
