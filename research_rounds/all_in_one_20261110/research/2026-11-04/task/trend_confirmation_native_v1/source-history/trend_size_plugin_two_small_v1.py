"""One frozen plan-size modifier over No60; no capacity cost guard hooks."""
from pathlib import Path
from decimal import Decimal as D
import copy, hashlib, importlib.util, json, sys
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'capacity_cost_guard_v1'))
import frozen_capacity_inputs as I
A,N,J,L,IO=I.A,I.N,I.J,I.L,I.IO
P=A.P
FEATURE_SOURCE=O.parent/'trend_confirmation_dedup_v1/compute_flags.py'
spec=importlib.util.spec_from_file_location('frozen_confirmation_flags_native',FEATURE_SOURCE)
F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
MANIFEST=A.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
ARMS=('B','UNIFORM50','A_ONLY','A_OR_B')
POLICY='NO60_ORIGINAL_LICENSED_INTENT_SIZE_CONFIRMATION_V1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class FeatureCache:
    def __init__(self,end):
        self.end=end;self.records={x['symbol']:x for x in json.loads(MANIFEST.read_text())}
        self.values={};self.sources={str(MANIFEST):sha(MANIFEST),str(FEATURE_SOURCE):sha(FEATURE_SOURCE)}
    def at(self,sid,day):
        if sid not in self.values:
            rec=self.records.get(sid)
            if not rec or rec['status']!='complete':
                self.values[sid]=None
            else:
                fp=Path(rec['refs']['facts'])
                sp=next(Path(p) for p in rec['source_sha256'] if p.endswith('/signal.parquet'))
                for p,h in [(fp,rec['output_sha256'][str(fp)]),(sp,rec['source_sha256'][str(sp)])]:
                    actual=sha(p);assert actual==h,('feature source changed',str(p));self.sources[str(p)]=actual
                f=pd.read_parquet(fp,columns=['close','segment_id','raw_close','factor']).loc[:self.end]
                s=pd.read_parquet(sp,columns=['close','segment_id','price_eligible','observed_bar','synthetic_event_bar']).loc[:self.end]
                original=s.reindex(f.index)
                observed=(original.price_eligible.astype('boolean') & original.observed_bar.astype('boolean')
                          & ~original.synthetic_event_bar.astype('boolean'))
                source_known=(np.isfinite(original.close.to_numpy(float)) & (original.close.to_numpy(float)>0)
                              & original.segment_id.notna().to_numpy())
                observed=observed & pd.Series(source_known,index=f.index)
                # Genuine unknown facts/source slots remain in the native clock
                # for compute_flags to mark UNKNOWN, not a wrapper assertion.
                both=(observed.fillna(False).to_numpy(bool)
                      & np.isfinite(f.close.to_numpy(float)) & (f.close.to_numpy(float)>0)
                      & f.segment_id.notna().to_numpy())
                assert np.allclose(f.close.to_numpy(float)[both],original.close.to_numpy(float)[both],rtol=1e-10,atol=1e-10)
                assert np.array_equal(f.segment_id.to_numpy()[both],original.segment_id.to_numpy()[both])
                self.values[sid]=F.compute_flags(f,price_observed=observed,debug=False)
        f=self.values[sid];t=pd.Timestamp(day)
        if f is None or t not in f.index:
            return dict(A=None,B=None,A_known=False,B_known=False,price_known=False,
                        m_A_ONLY=.5,m_A_OR_B=.5,reason='UNKNOWN_NO_EXACT_NATIVE_SOURCE')
        r=f.loc[t]
        return dict(A=None if pd.isna(r.A) else bool(r.A),B=None if pd.isna(r.B) else bool(r.B),
                    A_known=bool(r.A_known),B_known=bool(r.B_known),price_known=bool(r.price_known),
                    m_A_ONLY=float(r.m_A_ONLY),m_A_OR_B=float(r.m_A_OR_B),reason='EXACT_DECISION_CLOSE')


class Runner(A.Runner):
    def __init__(self,*args,feature_end,**kwargs):
        self._trend_ready=False
        super().__init__(*args,**kwargs)
        base=self.accounts['B'];self.accounts={}
        for name in ARMS:
            a=copy.copy(base)
            a.__dict__=copy.deepcopy({k:v for k,v in base.__dict__.items() if k not in ('market','facts')})
            a.market,a.facts,a.label=base.market,base.facts,name
            self.accounts[name]=a
        self.feature_cache=FeatureCache(feature_end)
        self.confirmation_events=[];self.opportunity_denominators=[]
        self.integration_policy=POLICY+':'+self.rank_mode
        self._trend_ready=True;self.assert_native_wiring()

    def assert_native_wiring(self):
        assert self.opening.__func__ is J.Runner.opening
        assert self.route.__func__ is P.ROUTES[True]
        assert self.planning.__func__ is Runner.planning
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        if getattr(self,'_trend_ready',False):
            assert self.integration_policy==POLICY+':'+self.rank_mode
        for a in self.accounts.values():
            assert type(a)is J.Account
            assert not hasattr(a,'capacity_alpha')
            expected=N.BASE.NoAccountBudget if getattr(self,'_cap_bootstrap',False) else A.NoConfirmed60Budget
            assert type(a.budget)is expected
            for meth in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,meth).__func__ is getattr(J.Account,meth)

    def planning(self,at):
        first=len(self.opportunities)
        # Keep original J planning, core sizing and complete PVR slot ordering.
        # Modification is AFTER N.apply_priority; removing a tiny plan cannot
        # silently permute the remaining original priority slots.
        N.Runner.planning(self,at)
        for name,a in self.accounts.items():
            d=a.decisions[-1];day=str(at.date());assert str(d['at'])[:10]==day
            if name=='B':continue # Exact original dictionaries and native flow.
            by={(x['sid'],x.get('role',x['kind'])):x for x in d['intents']}
            keep=[];retained=set()
            for intent in a.pending:
                sid=intent['sid'];role=intent.get('role',intent['kind']);key=(sid,role)
                logged=by[key];cap0=int(intent['cap']);budget0=D(intent['budget'])
                assert cap0==logged['cap'] and budget0==D(logged['budget'])
                assert cap0>0 and not intent.get('size_reject')
                flags=self.feature_cache.at(sid,day) if name!='UNIFORM50' else None
                m=D('.5') if name=='UNIFORM50' else D(str(flags['m_'+name]))
                rule=intent['quote'].quantity
                cap1=int(rule.buy_floor(int(D(cap0)*m)));budget1=budget0*m
                assert 0<=cap1<=cap0 and 0<=budget1<=budget0
                for row in (intent,logged):row['cap']=cap1;row['budget']=budget1
                result='kept' if cap1>0 else 'confirmation_half_below_minimum'
                self.confirmation_events.append(dict(account=name,at=at,sid=sid,role=role,
                    CP1_id=intent.get('CP1_id'),signal_epoch=intent.get('epoch'),
                    cap_before=cap0,budget_before=budget0,multiplier=m,cap_after=cap1,
                    budget_after=budget1,flags=flags,result=result,
                    priority_rank=intent['rank'],risk_budget_unchanged=intent.get('risk_budget'),
                    effective_after='NEXT_LEGAL_OPEN_NO_REAPPLICATION'))
                if cap1:
                    keep.append(intent);retained.add(key)
                else:
                    self.funding.append(dict(account=name,at=at,sid=sid,role=role,result=result))
            a.pending=keep
            d['intents']=[x for x in d['intents'] if (x['sid'],x.get('role',x['kind'])) in retained]
            assert len(a.pending)==len(d['intents'])
            daily=next(x for x in reversed(self.daily) if x['account']==name and str(x['at'])==str(at))
            daily['pending_intents']=len(a.pending)
        rows=self.opportunities[first:]
        self.opportunity_denominators.append(dict(at=at,full_rows=len(rows),
             retained_role_candidates=sum(bool(x['roles']) for x in rows),accounts=len(self.accounts)))
        self.opportunities[first:]=[x for x in rows if x['roles']]

    def dump_joint(self,path):
        J.Runner.dump_joint(self,path)
        IO.write_gzip_jsonl(Path(path)/'rank-policy.jsonl.gz',self.rank_log)
        IO.write_gzip_jsonl(Path(path)/'confirmation-size-events.jsonl.gz',self.confirmation_events,encoder=J.C.encoded)
        IO.write_gzip_jsonl(Path(path)/'opportunity-denominators.jsonl.gz',self.opportunity_denominators,encoder=J.C.encoded)
