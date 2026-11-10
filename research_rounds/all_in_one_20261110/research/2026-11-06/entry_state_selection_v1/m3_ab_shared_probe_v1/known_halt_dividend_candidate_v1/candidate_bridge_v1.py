"""Isolated, daily-only candidate adapter. No full-window/account entry point.
Native accounting, strategy, halt state, risk, reservation and layer code are reused.
"""
from pathlib import Path
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
from decimal import Decimal as D
import copy, hashlib, json, sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'known_halt_contract_v1'))
import engine_known_halt_v1 as native
from engine_known_halt_v1 import ARM,HALT,StateInvariantError,bridge
Layer=native.base.Layer
TZ=ZoneInfo('Asia/Shanghai')
EID='600403.SH|LOCAL_DISTRIBUTION_007'
REAL_SESSIONS=frozenset(('2022-04-14','2022-04-15','2022-04-18','2022-05-10','2022-05-11','2022-05-12','2022-05-13'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

def clock_bound(proof):
    """Validated reconstructed PUBLIC upper bound, never an earliest/PIT clock.
    Missing/contradictory timezone/date provenance is UNKNOWN, not local guessing.
    """
    try:
        if proof.get('timezone')!='Asia/Shanghai':return None,'TIMEZONE_UNVERIFIED'
        kind=proof.get('kind')
        if kind=='OFFICIAL_PUBLICATION_DATE':
            if proof.get('date_basis') not in ('OFFICIAL_ISSUE_DATE','EXPLICIT_OFFICIAL_PUBLICATION_DATE') or proof.get('publication_date_verified') is not True:return None,'OFFICIAL_PUBLICATION_DATE_UNPROVEN'
            day=date.fromisoformat(proof['publication_date'])
            return datetime.combine(day,time.max,TZ),'OFFICIAL_DATE_END_OF_DAY'
        if kind=='RELIABLE_NEWS_PAIRED_FACTS':
            if proof.get('clock_verified') is not True or proof.get('exact_fact_pair_verified') is not True or not proof.get('paired_facts'):return None,'NEWS_CLOCK_OR_FACT_PAIR_UNPROVEN'
            pub=datetime.fromisoformat(proof['published_at'])
            if pub.tzinfo is None:return None,'MISSING_TIMEZONE'
            vals=[pub]
            if proof.get('updated_at'):
                upd=datetime.fromisoformat(proof['updated_at'])
                if upd.tzinfo is None:return None,'MISSING_UPDATE_TIMEZONE'
                if upd<pub:return None,'CONFLICTING_PUBLICATION_UPDATE'
                vals.append(upd)
            # If current content was edited, no evidence it contained these facts
            # at the first publication time. Use the later update conservatively.
            bound=max(vals).astimezone(TZ)
            if proof.get('body_local_time'):
                body=datetime.fromisoformat(proof['body_local_time'])
                if body.tzinfo is None or body.astimezone(TZ)!=bound:return None,'CONFLICTING_BODY_CLOCK'
            return bound,'VERIFIED_NEWS_CURRENT_FACTS_UPPER_BOUND'
        return None,'EFFECTIVE_DATE_URL_DATE_OR_UNSUPPORTED_CLOCK'
    except (KeyError,TypeError,ValueError):return None,'MISSING_OR_MALFORMED_CLOCK'

def known_for_session(proof,session):
    bound,reason=clock_bound(proof)
    try:day=date.fromisoformat(str(session)[:10])
    except ValueError:return False,None,'INVALID_SESSION'
    if bound is None:return False,None,reason
    if proof.get('kind')=='OFFICIAL_PUBLICATION_DATE':
        if bound.date()>=day:return False,bound,'NOT_A_SUBSEQUENT_DAILY_SESSION'
    elif bound>=datetime.combine(day,time(9,30),TZ):
        return False,bound,'NEWS_NOT_STRICTLY_BEFORE_SESSION_OPEN'
    return True,bound,reason

def verify_artifacts(proof,synthetic=False):
    if synthetic:return {}
    arts=proof.get('artifacts',[])
    required=2 if proof.get('kind')=='RELIABLE_NEWS_PAIRED_FACTS' else 1
    if len(arts)<required:raise ValueError('Missing fact/clock evidence artifacts')
    out={}
    for a in arts:
        if not a.get('url'):raise ValueError('Missing evidence URL')
        actual=sha(a['path'])
        if actual!=a['sha256']:raise ValueError('Evidence hash changed: '+a['path'])
        out[a['path']]=actual
    return out

class HaltEvidence:
    """Same get(sid,day)/hashes/synthetic interface as the frozen halt consumer."""
    def __init__(self,rows=(),*,synthetic=False):
        self.rows=copy.deepcopy(tuple(rows));self.synthetic=synthetic;self.hashes={};seen=set()
        for r in self.rows:
            key=r['sid'],r['session']
            if key in seen:raise ValueError('Duplicate/conflicting session evidence')
            seen.add(key);self.hashes.update(verify_artifacts(r['clock'],synthetic))
    def get(self,sid,day):
        for r in self.rows:
            if (r['sid'],r['session'],r.get('scope'))!=(sid,str(day.date()),'FULL_DAY'):continue
            ok,bound,reason=known_for_session(r['clock'],day)
            if ok:return dict(r,known_at=bound.isoformat(),clock_admission=reason)
        return None

class CandidateTape:
    """Only a limited candidate runtime selection. Original catalog stays intact.
    Preannounced facts and time-local observed coordinate are separate objects.
    """
    def __init__(self,source,candidates=(),*,synthetic=False):
        self.s=source;self.candidates=copy.deepcopy(tuple(candidates));self.synthetic=synthetic
        self.hashes={};self.audit=[];ids=set()
        self.original_event_ids=tuple(e['economic_event_id'] for e in source.EVENTS)
        for c in self.candidates:
            eid=c['economic_event_id']
            if eid in ids or (not synthetic and eid in self.original_event_ids):raise ValueError('Duplicate/overwritten economic event identity')
            ids.add(eid)
            if c['event_type']!='PURE_CASH' or D(c['split_ratio'])!=1:raise ValueError('Only pure cash candidate supported')
            if any(x in c for x in ('factor_old','factor_new','previous_close','previous_day')):raise ValueError('Future market coordinate in public announcement object')
            self.hashes.update(verify_artifacts(c['clock'],synthetic))
            if not (c['record_date']<c['ex_date']<=c['pay_date']):raise ValueError('Invalid pure cash dates')
    def announcement(self,c,day):
        ok,bound,reason=known_for_session(c['clock'],day)
        if not ok:return None
        return dict(sid=c['sid'],economic_event_id=c['economic_event_id'],event_type='PURE_CASH',
            evidence_version=digest(c),record_date=self.s.pd.Timestamp(c['record_date']),coordinate_snapshot_day=self.s.pd.Timestamp(c['record_date']),
            ex_date=self.s.pd.Timestamp(c['ex_date']),pay_date=self.s.pd.Timestamp(c['pay_date']),
            d_source=D(c['d_source']),d_cash=D(c['d_cash']),entitlement_verified=True,
            coordinate_verified=False,entitlement_scope='OWN_REGISTER_Q_NET80_NOT_ACTUAL_TAX',
            public_known_upper_bound=bound.isoformat(),public_clock_basis=reason,
            evidence_domain='CURRENT_HISTORICAL_FACTS_NOT_PIT',origin='LIMITED_CANDIDATE_V1')
    def project(self,day,phase):
        s=self.s;visible=[];at={};record={};ex={};pay={}
        for c in self.candidates:
            e=self.announcement(c,day)
            if e is None:continue
            record.setdefault(e['record_date'],[]).append(e)
            # Only at the ex session OPEN or later: never reads ex raw/factor
            # while learning the May 5 announcement on May 6.
            if day>=e['ex_date']:
                previous=s.cal[s.cal<e['ex_date']][-1]
                z=s.raw[c['sid']].get(e['ex_date'],{});p=s.raw[c['sid']].get(previous,{})
                def dec(v):
                    try:return D(str(v))
                    except Exception:return D('NaN')
                e.update(previous_day=previous,previous_close=dec(p.get('raw_close')),
                    factor_old=dec(p.get('adjustment_factor')),factor_new=dec(z.get('adjustment_factor')),
                    coordinate_observed_at=(e['ex_date'],'OPEN'),coordinate_scope='NATIVE_DAILY_FACTOR_TRANSLATION_ONLY')
                valid=previous==e['record_date'] and s.coordinate_matches(e,z,p)
                e['coordinate_verified']=bool(valid)
                at[(e['sid'],e['ex_date'])]=e
                ex.setdefault(e['ex_date'],[]).append(e);pay.setdefault(e['pay_date'],[]).append(e)
                self.audit.append(dict(type='TIME_LOCAL_COORDINATE_CHECK',at=(day,phase),eid=e['economic_event_id'],valid=bool(valid),previous_day=previous,previous_close=e['previous_close'],factor_old=e['factor_old'],factor_new=e['factor_new']))
            visible.append(e)
        # Runtime maps belong to this disposable source instance. Native original
        # definitions and registry files are never rewritten or re-authorized.
        s.EVENT_AT=at;s.BY_RECORD=record;s.BY_EX=ex;s.BY_PAY=pay
        s.ALLOWED_EVENT_IDS={e['economic_event_id'] for e in visible}
        return visible

class ExecutionBridge(native.ExecutionBridge):
    def __init__(self,*args,candidates=(),synthetic_candidates=False,**kw):
        if kw.get('evidence_domain') not in ('SYNTHETIC_SOURCE_DEFINITION','REAL_DAILY_CONDITIONAL_FIXTURE'):raise StateInvariantError('Candidate has no full-account release')
        super().__init__(*args,**kw)
        self.candidate_tape=CandidateTape(self.s,candidates,synthetic=synthetic_candidates)
        self.source_hashes.update(self.candidate_tape.hashes)
        self.bounded_real=self.evidence_domain=='REAL_DAILY_CONDITIONAL_FIXTURE'
        if self.bounded_real:
            if self.halts.synthetic or synthetic_candidates:raise StateInvariantError('Synthetic evidence cannot enter a real daily fixture')
            if any((r['sid'],r['session'])!=('600403.SH','2022-04-15') for r in self.halts.rows):raise StateInvariantError('Outside finite 600403 halt candidate')
            if any(c['economic_event_id']!=EID for c in candidates):raise StateInvariantError('Outside finite 600403 distribution candidate')
    def _stage(self,day,phase):
        if self.bounded_real and str(self.s.pd.Timestamp(day).date()) not in REAL_SESSIONS:raise StateInvariantError('Outside frozen daily fixture dates')
        super()._stage(day,phase)
        self.candidate_tape.project(self.day,phase)
