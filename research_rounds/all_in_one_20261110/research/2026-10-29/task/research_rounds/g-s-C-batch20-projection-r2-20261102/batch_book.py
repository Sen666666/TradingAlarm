"""Opportunity authorisation mirror only; never a cash or execution ledger.

Observed layer duties use the native trim stable-prefix union convention.
Synthesis supplies explicit observations; no financial callbacks are installed.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
import copy,json,hashlib

MANDATORY={'original_protection_failure','ACT_exit','original_price_support_failure'}
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def aware(s):
    t=datetime.fromisoformat(s)
    if t.tzinfo is None:raise ValueError('aware clock required')
    return t
def decimal(x):
    if x is None:raise ValueError('UNKNOWN monetary/quantity basis')
    z=D(x)
    if not z.is_finite():raise ValueError('UNKNOWN nonfinite value')
    return z
def integer(x):
    z=decimal(x)
    if z!=int(z):raise ValueError('fractional native quantity unsupported')
    return int(z)

class BatchBook:
    def __init__(self,account_id,source_binding,lines,proof_registry=None):
        if not account_id or not source_binding:raise ValueError('identity required')
        self.account_id=account_id;self.source_binding=source_binding
        self.lines={str(z['layer']):copy.deepcopy(z) for z in lines};self.proofs=copy.deepcopy(proof_registry or {})
        if len(self.lines)!=len(lines):raise ValueError('duplicate assigned layer')
        self.batch=None;self.plans={};self.history=[];self.observation_ids=set();self.observation_payloads={};self.last_observed_at=None
        for key,z in self.lines.items():
            z.update(layer=key,qty=integer(z['qty']),opp=integer(z.get('opp',0)),mandatory=integer(z.get('mandatory',0)),
                relative_ratio=str(z.get('relative_ratio','1')),cancel_pending=bool(z.get('cancel_pending',False)))
            if not 0<=max(z['opp'],z['mandatory'])<=z['qty']:raise ValueError('duty union exceeds observed inventory')
            if decimal(z['relative_ratio'])<=0:raise ValueError('nonpositive quantity ratio')
            if z['mandatory'] and z.get('mandatory_proof_id') not in self.proofs:raise ValueError('UNKNOWN independent mandatory proof')
    def commitments(self):
        return copy.deepcopy(self.lines)
    def _time(self,at):
        t=aware(at)
        if self.last_observed_at and t<aware(self.last_observed_at):raise ValueError('out-of-order observation/decision')
        if self.batch and t<aware(self.batch['cursor']):raise ValueError('observation precedes frozen decision')
        self.last_observed_at=at
    def _source(self,source_binding):
        if source_binding!=self.source_binding:raise ValueError('wrong observation source')
    def begin(self,cursor,nav,marks,*,known_at=None):
        aware(cursor);known_at=known_at or cursor
        if aware(known_at)>aware(cursor):raise ValueError('future marks')
        marks={str(k):str(decimal(v)) for k,v in marks.items()}
        if any(decimal(v)<=0 for v in marks.values()):raise ValueError('nonpositive mark')
        if decimal(nav)<=0:raise ValueError('nonpositive NAV cannot open opportunity budget')
        if self.batch and cursor==self.batch['cursor']:
            if str(decimal(nav))!=self.batch['NAV'] or marks!=self.batch['marks']:raise ValueError('same batch already frozen')
            return self.batch
        if self.batch and aware(cursor)<=aware(self.batch['cursor']):raise ValueError('cursor replay cannot open budget')
        carry=D(0);snapshot=copy.deepcopy(self.lines)
        for key,z in snapshot.items():
            if not 0<=max(z['opp'],z['mandatory'])<=z['qty']:raise ValueError('quantity union mismatch')
            if z['mandatory']:
                p=self.proofs[z['mandatory_proof_id']]
                if p['kind'] not in MANDATORY or str(p['layer'])!=key or aware(p['known_at'])>aware(cursor):raise ValueError('invalid/future independent mandatory proof')
                proof_qty=decimal(p['qty'])*decimal(z['relative_ratio'])/decimal(p['relative_ratio'])
                if D(z['mandatory'])>proof_qty:raise ValueError('mandatory exceeds independently proven quantity')
            healthy=max(0,z['opp']-z['mandatory'])
            if healthy:
                if key not in marks:raise ValueError('UNKNOWN carry mark')
                carry+=D(healthy)*decimal(marks[key])
        self._time(cursor)
        self.batch=dict(cursor=cursor,id=self.account_id+'|'+cursor,NAV=str(decimal(nav)),limit=str(decimal(nav)*D('.2')),
            marks=marks,known_at=known_at,carry=str(carry),new='0',frozen_lines=snapshot,approved=[])
        self.history.append(dict(kind='new_batch',batch=copy.deepcopy(self.batch)))
        return self.batch
    def preview(self,requests):
        if self.batch is None:raise ValueError('no frozen batch')
        details=[];charge=D(0)
        for key,qty in requests.items():
            key=str(key);q=integer(qty)
            if not q:continue
            if key not in self.lines or key not in self.batch['marks']:raise ValueError('UNKNOWN assigned layer or mark')
            z=self.lines[key]
            if q<0 or q>z['qty']:raise ValueError('requested prefix exceeds native observed inventory')
            before=max(0,z['opp']-z['mandatory']);after=max(0,max(z['opp'],q)-z['mandatory'])
            added=after-before;basis=decimal(self.batch['marks'][key])
            # Convert current raw quantities back to this batch's frozen unit domain.
            ratio=decimal(z['relative_ratio'])/decimal(self.batch['frozen_lines'][key]['relative_ratio'])
            amount=D(added)/ratio*basis;charge+=amount
            details.append(dict(layer=key,requested_prefix=q,opp_before=z['opp'],mandatory_prefix=z['mandatory'],
                native_union=max(z['mandatory'],z['opp'],q),healthy_new_qty=added,gross=str(amount)))
        used=decimal(self.batch['carry'])+decimal(self.batch['new']);limit=decimal(self.batch['limit'])
        # An inherited overhang blocks new D, while D=0/freecash remains legal.
        ok=(charge==0 or used+charge<=limit)
        return dict(ok=ok,carry=self.batch['carry'],already_new=self.batch['new'],additional=str(charge),existing_overhang=used>limit,
            limit=str(limit),residual=str(limit-used-charge),lines=details)
    def approve(self,plan_id,requests,*,target_binding):
        body=dict(batch=self.batch['id'],requests={str(k):integer(v) for k,v in requests.items() if v},target_binding=target_binding)
        if plan_id in self.plans:
            if self.plans[plan_id]['body']!=body:raise ValueError('same plan identity changed; cannot refresh budget')
            return copy.deepcopy(self.plans[plan_id])
        preview=self.preview(body['requests'])
        if not preview['ok']:raise ValueError('opportunity_batch20_exhausted')
        if body['requests'] and decimal(preview['additional'])==0:raise ValueError('existing duty cannot fund unrelated new plan twice')
        entry=dict(body=body,charge=preview['additional'],details=preview['lines'])
        self.plans[plan_id]=entry;self.batch['approved'].append(plan_id)
        self.batch['new']=str(decimal(self.batch['new'])+decimal(entry['charge']))
        for d in preview['lines']:self.lines[d['layer']]['opp']=max(self.lines[d['layer']]['opp'],d['requested_prefix'])
        return copy.deepcopy(entry)
    def mandatory(self,key,qty,proof_id,*,at):
        qty=integer(qty)
        if proof_id not in self.proofs:raise ValueError('independent proof not in trusted registry')
        p=self.proofs[proof_id];key=str(key)
        if decimal(p['relative_ratio'])<=0:raise ValueError('UNKNOWN independent quantity basis')
        if p['kind'] not in MANDATORY or str(p['layer'])!=key or int(p['qty'])!=qty:raise ValueError('not an original independent mandatory proof')
        if aware(p['known_at'])>aware(at):raise ValueError('future mandatory proof')
        z=self.lines[key]
        if qty<0 or qty>z['qty']:raise ValueError('mandatory quantity exceeds native inventory')
        self._time(at)
        z['mandatory']=max(z['mandatory'],qty)
        z['mandatory_proof_id']=proof_id
        self.history.append(dict(kind='independent_mandatory',layer=key,qty=qty,proof_id=proof_id,at=at,
            union=max(z['opp'],z['mandatory']),budget_refunded=False))
    def shrink(self,key,qty,*,at,source_binding):
        self._source(source_binding);qty=integer(qty)
        z=self.lines[str(key)]
        if not 0<=qty<=z['opp']:raise ValueError('not a shrink')
        self._time(at)
        z['opp']=qty # Current batch carry/new charge deliberately unchanged.
    def cancel_request(self,key,*,at,source_binding):
        self._source(source_binding);self._time(at);self.lines[str(key)]['cancel_pending']=True
    def cancel_ack(self,key,*,at,source_binding):
        self._source(source_binding)
        z=self.lines[str(key)]
        if not z['cancel_pending']:raise ValueError('no cancel request')
        if z['mandatory']:raise ValueError('cannot cancel an independent mandatory union')
        self._time(at)
        z['opp']=0;z['cancel_pending']=False
    def observe_fill(self,key,qty,price,receipt_id,*,source_binding,at):
        self._source(source_binding);qty=integer(qty)
        if decimal(price)<=0:raise ValueError('nonpositive observed price')
        payload=dict(layer=str(key),qty=qty,price=str(decimal(price)),source_binding=source_binding,at=at)
        if receipt_id in self.observation_ids:
            if self.observation_payloads[receipt_id]!=payload:raise ValueError('same observation identity changed')
            return
        aware(at);z=self.lines[str(key)]
        if qty<=0 or qty>max(z['opp'],z['mandatory']) or qty>z['qty']:raise ValueError('fill exceeds designated union')
        self._time(at)
        z['opp']=max(0,z['opp']-qty);z['mandatory']=max(0,z['mandatory']-qty);z['qty']-=qty
        self.observation_ids.add(receipt_id);self.observation_payloads[receipt_id]=payload;self.history.append(dict(kind='observed_fill',layer=str(key),qty=qty,
            actual_gross=str(D(qty)*decimal(price)),receipt_id=receipt_id,at=at,budget_refunded=False,cash_changed_by_book=False))
    def observe_split(self,key,ratio,*,at,source_binding):
        self._source(source_binding)
        z=self.lines[str(key)];r=decimal(ratio)
        if r<=0:raise ValueError('invalid split')
        changed={k:decimal(z[k])*r for k in ('qty','opp','mandatory')}
        if any(v!=int(v) for v in changed.values()):raise ValueError('unsupported fractional duty; reject before mutation')
        self._time(at)
        z.update({k:int(v) for k,v in changed.items()});z['relative_ratio']=str(decimal(z['relative_ratio'])*r)
    def dumps(self):
        body=dict(account_id=self.account_id,source_binding=self.source_binding,lines=self.lines,proofs=self.proofs,batch=self.batch,
            plans=self.plans,history=self.history,observation_ids=sorted(self.observation_ids),observation_payloads=self.observation_payloads,last_observed_at=self.last_observed_at)
        return json.dumps(dict(body=body,state_id=digest(body)),sort_keys=True,default=str)
    @classmethod
    def loads(cls,text,*,trusted_sha256,account_id,source_binding,actual_commitments):
        if hashlib.sha256(text.encode()).hexdigest()!=trusted_sha256:raise ValueError('trusted checkpoint bytes changed')
        x=json.loads(text);b=x['body']
        if x['state_id']!=digest(b):raise ValueError('state body digest')
        if b['account_id']!=account_id or b['source_binding']!=source_binding:raise ValueError('checkpoint identity mismatch')
        if b['lines']!=actual_commitments:raise ValueError('observed commitments mismatch')
        r=cls(account_id,source_binding,[],b['proofs']);r.lines=b['lines'];r.batch=b['batch'];r.plans=b['plans'];r.history=b['history'];r.observation_ids=set(b['observation_ids']);r.observation_payloads=b['observation_payloads'];r.last_observed_at=b['last_observed_at']
        if r.batch:
            used=sum((decimal(r.plans[p]['charge']) for p in r.batch['approved']),D(0))
            if used!=decimal(r.batch['new']):raise ValueError('authorisation charge conservation')
        return r

if __name__=='__main__':
    import sys
    ip=Path(sys.argv[1]);text=ip.read_text();obs=json.loads(Path(sys.argv[3]).read_text())
    b=BatchBook.loads(text,trusted_sha256=sys.argv[2],account_id=obs['account_id'],source_binding=obs['source_binding'],actual_commitments=obs['lines'])
    assert decimal(b.batch['new'])==decimal(obs['expected_new'])
    assert b.preview(obs['attempt'])['ok']==obs['expected_allowed']
    out=Path(sys.argv[4]);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(dict(exact=b.dumps()==text,new=b.batch['new'],attempt_allowed=b.preview(obs['attempt'])['ok'],scope='budget component, no installed native account callback',financial_events=0),indent=2)+'\n')
