"""Read-only frozen CE input/ranking adapter. No account state, admission, K, or label use."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent

def _sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class CELookup:
    """Exact (sid, signal_day) lookup for every original cached fresh CP in fixed1709.

    No interpolation, previous-receipt carry, synthesized indicator, held-state filter,
    score threshold, trade delay, top-K truncation, or cash/position decision.
    """
    def __init__(self,directory=None,verify_hashes=True):
        self.directory=Path(directory) if directory is not None else ROOT
        self.metadata=json.loads((self.directory/'ADAPTER_MANIFEST.json').read_text())
        if verify_hashes:
            for name,h in self.metadata['artifact_sha256'].items():
                if _sha(self.directory/name)!=h:raise ValueError('Frozen adapter artifact hash mismatch: '+name)
        self.stocks=pd.read_csv(self.directory/'STOCK_COVERAGE.csv',keep_default_na=False).set_index('sid')
        self.scores=pd.read_parquet(self.directory/'ALL_NATIVE_CP_RECEIPT_CE.parquet').set_index(['sid','day'])
        if self.scores.index.has_duplicates:raise ValueError('Duplicate native CP receipt key')

    def query(self,sid,day):
        """Return dict with CE, CE_known, reason, formation_n, V, source evidence.

        Missing source/day/fresh receipt or forecast warm-up returns NaN, never a
        filled value. Caller must retain its original PVR slot on any UNKNOWN.
        """
        sid=str(sid);day=str(pd.Timestamp(day).date());key=(sid,day)
        if sid not in self.stocks.index:
            return dict(sid=sid,day=day,CE=math.nan,CE_known=False,reason='outside_fixed1709_pool')
        s=self.stocks.loc[sid]
        if s.source_status!='complete':
            return dict(sid=sid,day=day,CE=math.nan,CE_known=False,reason='source_unavailable:'+str(s.source_status))
        if key not in self.scores.index:
            return dict(sid=sid,day=day,CE=math.nan,CE_known=False,reason='no_original_cached_fresh_CP_on_requested_day')
        z=self.scores.loc[key].to_dict();z.update(sid=sid,day=day)
        z['CE_known']=bool(np.isfinite(z['CE']));z['reason']='known_original_fresh_CP' if z['CE_known'] else 'unknown_formation_variance_or_warm_history'
        return z

    def score_candidates(self,frame):
        """Return original rows plus frozen score/status. No row is removed.

        Required columns: sid, day. Existing CE fields are replaced with authoritative
        adapter values. Unrelated candidate/account fields are preserved unchanged.
        """
        if not {'sid','day'}<=set(frame):raise ValueError('sid/day required')
        out=frame.copy();queries=[self.query(s,d) for s,d in zip(out.sid,out.day)]
        out['CE']=[q['CE'] for q in queries];out['CE_known']=[q['CE_known'] for q in queries];out['CE_status']=[q['reason'] for q in queries]
        out['CE_formation_n']=[q.get('formation_n',math.nan) for q in queries]
        out['CE_variance_budget']=[q.get('variance_budget',math.nan) for q in queries]
        return out

    def rank_frame(self,frame):
        """Rank one ORIGINAL legal EMPTY/fresh-CP MOBILE queue, WITHOUT truncation.

        Required sid/day/original_PVR/original_priority_rank. Caller must form the
        queue under its own counterfactual live account state and unchanged rules.
        Original priority/sid determines slots. Finite CE AND finite PVR slots only
        are permuted by CE.round12 desc, PVR.round12 desc, priority/sid asc.
        CE-unknown and PVR-unknown rows stay in exact original slots.
        All rows return, with CE_original_slot and CE_rank. Caller keeps its original
        cash/position/industry/lot-size/execution rules; this method has no K=20.
        """
        required={'sid','day','original_PVR','original_priority_rank'}
        if not required<=set(frame):raise ValueError('Missing queue columns: '+str(required-set(frame)))
        if len(frame) and frame.day.nunique()!=1:raise ValueError('rank_frame requires exactly one signal day')
        if frame.sid.duplicated().any():raise ValueError('rank_frame requires one candidate per sid in a queue')
        scored=self.score_candidates(frame).reset_index(drop=True)
        base=scored.sort_values(['original_priority_rank','sid'],kind='stable').copy()
        base['CE_original_slot']=range(1,len(base)+1)
        base['CE_slot_replaceable']=base.CE_known & np.isfinite(base.original_PVR)
        known=base[base.CE_slot_replaceable].copy();known['_ce_r12']=known.CE.round(12);known['_pvr_r12']=known.original_PVR.round(12)
        known=known.sort_values(['_ce_r12','_pvr_r12','original_priority_rank','sid'],ascending=[False,False,True,True],kind='stable')
        it=iter(known.index);ix=[next(it) if base.at[i,'CE_slot_replaceable'] else i for i in base.index]
        out=base.loc[ix].copy();out['CE_rank']=range(1,len(out)+1)
        assert len(out)==len(frame)
        fixed=out[~out.CE_slot_replaceable];assert fixed.CE_original_slot.eq(fixed.CE_rank).all()
        return out.reset_index(drop=True)
