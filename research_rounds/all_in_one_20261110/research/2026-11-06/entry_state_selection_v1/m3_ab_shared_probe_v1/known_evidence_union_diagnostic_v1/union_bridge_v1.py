"""Isolated 436+1 union; no legacy event re-adjudication, no economic entrypoint."""
from pathlib import Path
from decimal import Decimal as D
import sys, copy, json
HERE=Path(__file__).resolve().parent;B=HERE.parent
sys.path.insert(0,str(B/'known_halt_dividend_candidate_v1'))
import candidate_bridge_v1 as C
native=C.native;bridge=C.bridge;ARM=C.ARM;HALT=C.HALT;Layer=C.Layer
from halt_evidence_v1 import HaltEvidence as LegacyHalts
sha=C.sha;digest=C.digest
CATALOG=B/'known_halt_dividend_candidate_v1/CANDIDATES_V1.json'
LEGACY_HALT=B/'known_halt_contract_v1/HALT_EVIDENCE_V1.json'

class UnionHalts:
    def __init__(self):
        old=LegacyHalts.load(LEGACY_HALT);catalog=json.loads(CATALOG.read_text())
        new=C.HaltEvidence(catalog['halts'])
        assert {(r['sid'],r['session']) for r in old.rows}=={('600595.SH','2022-01-13')}
        assert {(r['sid'],r['session']) for r in new.rows}=={('600403.SH','2022-04-15')}
        self.parts=(old,new);self.rows=tuple(old.rows)+tuple(new.rows);self.synthetic=False
        self.hashes=dict(old.hashes,**new.hashes);self.hashes[str(CATALOG)]=sha(CATALOG)
    def get(self,sid,day):
        rows=[r for x in self.parts if (r:=x.get(sid,day)) is not None]
        if len(rows)>1:raise ValueError('Conflicting halt identity')
        return rows[0] if rows else None

class UnionTape:
    """All runtime catalog views project the same old-preserving union.
    New future market coordinates never reside in public announcement objects.
    Old events retain their original evidence limits and permission exactly.
    """
    def __init__(self,s,candidates=(),*,synthetic=False):
        self.s=s;self.old_events=copy.deepcopy(s.EVENTS)
        self.old_allowed=copy.deepcopy(s.ALLOWED_EVENT_IDS)
        self.old_maps=copy.deepcopy({k:getattr(s,k) for k in ('EVENT_BY_ID','EVENT_AT','BY_RECORD','BY_EX','BY_PAY')})
        ids=[e['economic_event_id'] for e in self.old_events];keys=[(e['sid'],e['ex_date']) for e in self.old_events]
        if len(ids)!=len(set(ids)) or len(keys)!=len(set(keys)):raise ValueError('Legacy catalog collision')
        seen_ids=set(ids);seen_keys=set(keys)
        for c in candidates:
            key=(c['sid'],s.pd.Timestamp(c['ex_date']));eid=c['economic_event_id']
            if eid in seen_ids or key in seen_keys:raise ValueError('Union ID or sid/ex collision')
            seen_ids.add(eid);seen_keys.add(key)
        self.candidate=C.CandidateTape(s,candidates,synthetic=synthetic)
        self.hashes=self.candidate.hashes;self.audit=self.candidate.audit
        self.old_digest=digest(self.old_events)
    def project(self,day,phase):
        s=self.s;day=s.pd.Timestamp(day)
        for c in self.candidate.candidates:
            if day>=s.pd.Timestamp(c['ex_date']) and self.candidate.announcement(c,day) is not None:s.load(c['sid'])
        visible=self.candidate.project(day,phase)
        new_maps={k:getattr(s,k) for k in ('EVENT_AT','BY_RECORD','BY_EX','BY_PAY')}
        s.EVENTS=list(self.old_events)+visible
        s.EVENT_BY_ID=dict(self.old_maps['EVENT_BY_ID'],**{e['economic_event_id']:e for e in visible})
        s.EVENT_AT=dict(self.old_maps['EVENT_AT']);s.EVENT_AT.update(new_maps['EVENT_AT'])
        for name in ('BY_RECORD','BY_EX','BY_PAY'):
            merged={d:list(rows) for d,rows in self.old_maps[name].items()}
            for d,rows in new_maps[name].items():merged.setdefault(d,[]).extend(rows)
            setattr(s,name,merged)
        permitted={e['economic_event_id'] for e in self.old_events} if self.old_allowed is None else set(self.old_allowed)
        s.ALLOWED_EVENT_IDS=permitted|{e['economic_event_id'] for e in visible}
        assert digest(s.EVENTS[:len(self.old_events)])==self.old_digest
        return visible

class ExecutionBridge(native.ExecutionBridge):
    def __init__(self,s,*args,candidates=None,synthetic_candidates=False,**kw):
        # This is a new isolated adapter, not a widened CandidateBridge domain.
        super().__init__(s,*args,**kw)
        if candidates is None:candidates=json.loads(CATALOG.read_text())['distributions']
        if self.evidence_domain=='REAL_FROZEN_SOURCE':
            if synthetic_candidates or candidates!=json.loads(CATALOG.read_text())['distributions'] or not isinstance(self.halts,UnionHalts):raise ValueError('Real union scope mismatch')
            if len(s.EVENTS)!=436:raise ValueError('Original domain changed')
        self.union_tape=UnionTape(s,candidates,synthetic=synthetic_candidates)
        self.source_hashes.update(self.union_tape.hashes)
    def _stage(self,day,phase):
        super()._stage(day,phase);self.union_tape.project(self.day,phase)
    @property
    def candidate_tape(self):return self.union_tape
    def capture_runtime(self):
        r=super().capture_runtime()
        r['union']=copy.deepcopy(dict(candidate_audit=self.union_tape.audit,old_events=self.union_tape.old_events,old_maps=self.union_tape.old_maps,old_allowed=self.union_tape.old_allowed,
            runtime_catalog={k:getattr(self.s,k) for k in ('EVENTS','EVENT_BY_ID','EVENT_AT','BY_RECORD','BY_EX','BY_PAY','ALLOWED_EVENT_IDS','BRIDGE','MODE')},
            source_hashes=self.source_hashes,source_data_hashes=self.s.hashes,cp_cache=self.cp_cache,
            meta=self.s.meta,load_count=self.s.load_count,loaded_sids=list(self.s.raw),actions_sources=self.s.actions_sources,
            seed_cash=self.seed_cash,evidence_domain=self.evidence_domain,halt_rows=self.halts.rows))
        return r
    def restore_runtime(self,r):
        super().restore_runtime(r);u=copy.deepcopy(r['union'])
        self.union_tape.old_events=u['old_events'];self.union_tape.old_maps=u['old_maps'];self.union_tape.old_allowed=u['old_allowed']
        self.union_tape.candidate.audit=u['candidate_audit'];self.union_tape.audit=self.union_tape.candidate.audit
        for k,v in u['runtime_catalog'].items():setattr(self.s,k,v)
        self.source_hashes=u['source_hashes'];self.s.hashes=u['source_data_hashes'];self.cp_cache=u['cp_cache']
        self.s.meta=u['meta'];self.s.actions_sources=u['actions_sources'];self.s.load_count=u['load_count']
        self.seed_cash=u['seed_cash'];self.evidence_domain=u['evidence_domain']

def responsibilities(b,rid):
    if rid not in b.s.archives:raise native.StateInvariantError('UNKNOWN or snapshot round has no authoritative archive: '+rid)
    st=b.s.archives[rid]
    claims=[c for c in b._claims_for(rid) if not c.get('settled',False)]
    orders=b._live_orders(rid=rid)
    layers=[x for x in b.layers if x.round_id==rid and x.qty>0]
    qty=int(st.get('core',0))+int(st.get('add',0));recv=D(str(st.get('receivable',0)))
    pending=bool(st.get('exitpending') or st.get('addexitpending'))
    liable=bool(qty or recv or claims or orders or layers or pending)
    return dict(has_responsibility=liable,core=st.get('core',0),add=st.get('add',0),receivable=recv,
        unsettled_claims=copy.deepcopy(claims),live_orders=copy.deepcopy(orders),active_layers=copy.deepcopy(layers),
        exitpending=st.get('exitpending'),addexitpending=st.get('addexitpending'),addpending=st.get('addpending'),
        liability_free_never_filled=b._zero_liability_initial_unknown(rid,st))

def blocking_unknowns(b,day,phase):
    """Only after a whole original OPEN or CLOSE returns; never reserve/fill interruption.
    State UNKNOWN or snapshot asset/source UNKNOWN AND actual inventory, active
    layer, nonzero receivable, unsettled claim, live order, or pending sell.
    Prior historical fills/settled claims alone are NOT current responsibility.
    Evidence-supported halt/recovery-lock NAV gaps alone are NOT UNKNOWN.
    """
    found={}
    for sid,st in b.states.items():
        if st.get('state')=='UNKNOWN':found[(st['round_id'],st.get('unknown_reason'))]=dict(sid=sid,round_id=st['round_id'],reason=st.get('unknown_reason'),origin='STATE')
    for row in b.snapshot(day,phase).unknown:
        found.setdefault((row['round_id'],row.get('reason')),dict(row,origin='SNAPSHOT'))
    out=[]
    for row in found.values():
        responsibility=responsibilities(b,row['round_id'])
        if responsibility['has_responsibility']:
            out.append(dict(row,at=(day,phase),responsibility=responsibility))
    # Native termination records retain emission order across held exits and initial checks.
    indexes={r['round_id']:i for i,r in enumerate(b.s.rounds) if r.get('failure_phase')==phase and r.get('status_day')==day}
    for row in out:row['source_termination_log_index']=indexes.get(row['round_id'])
    out.sort(key=lambda r:indexes.get(r['round_id'],len(b.s.rounds)))
    return out
