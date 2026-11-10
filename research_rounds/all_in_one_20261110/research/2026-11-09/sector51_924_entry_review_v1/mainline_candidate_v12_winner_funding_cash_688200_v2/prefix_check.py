"""Read-only strict economic and branch-content comparison to the certified v1 22 days."""
from pathlib import Path
import hashlib
import json
O=Path(__file__).resolve().parent
BASE=O.parent/'mainline_candidate_v12_winner_funding_competition/once_20250120'
DAILY={'ORDERS':'orders','CANDIDATES':'candidates','CP_EVENTS':'cp_log','DAY_LEDGER':'ledger','HOLDINGS':'holdings','EQUITY_EVENTS':'equity','SECTOR_DAILY':'sector_daily',
 'RETRY_TICKETS':'ticket_log','INFORMATION_CONFIRMATIONS':'confirmations','TRANSFERS':'transfers','FUNDING_REQUESTS':'request_details','ADD_FLOOR_RISK':'floor_risk','OPEN_SECTOR_EXPOSURE':'open_exposure',
 'AVAILABILITY_EVENTS':'availability','REFERENCE_DAILY':'reference_log','CAPITAL_LOTS':'capital_lots','REFERENCE_REQUESTS':'reference_requests',
 'EVENT_LOG':'event_log','EVENT_REQUEST_PLANS':'event_plans','SEED_FLOOR_RISK':'seed_floor_risk','SEED_COMMISSION_DIAGNOSTIC':'seed_execution_cost',
 'FUNDING_OPEN_DECISIONS':'funding_decisions','FUNDING_WAIT_LOG':'funding_wait_log','FUNDING_PREFLIGHT':'funding_preflight','FUNDING_ACTUAL_DIAGNOSTICS':'funding_actual'}
ENRICH={'ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY'}
FUNDING={'FUNDING_OPEN_DECISIONS','FUNDING_WAIT_LOG','FUNDING_PREFLIGHT','FUNDING_ACTUAL_DIAGNOSTICS'}
FINAL={'TICKET_STATE':'tickets','TRANSFER_PLAN_AT_END':'transfer_plan','REFERENCE_AT_END':'reference','EVENT_REGISTRY':'events','CURRENT_EVENT':'current_event','QUOTE_GAPS':'quote_gaps','FUNDING_WAIT_STATE':'funding_waits'}


def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def export_value(v,clean):return json.loads(json.dumps(clean(v) if clean else v,ensure_ascii=False,default=str))
def stream_hash(v,stream):
    # Only ONE baseline branch at a time (old22 max raw 5.53MB), never a book/tree.
    # Same pretty bytes as stream.json_chunks; C string encoding is much faster
    # for prefix verification. The actual 7GB output exporter stays fully streaming.
    return hashlib.sha256(json.dumps(stream.small_clean(v),ensure_ascii=False,indent=2,default=str).encode()).hexdigest()

def book_descriptor(book,branch_hashes):
    r={k:v for k,v in book.items() if k!='branches' and not k.startswith('_stream') and k not in ('_max_raw_branch_chars','_context')}
    if r['close_day']=='2024-10-10':
        assert r['scratch_integrity']['passed'] and r['scratch_integrity']['before']==r['scratch_integrity']['after']
        r.pop('book_id');r['scratch_integrity']={'passed':True}
    r['branches']=branch_hashes
    return r

class PrefixVerifier:
    def __init__(self,engine_module):
        self.e=engine_module;self.ref=json.loads((O/'PREFIX_REFERENCE.json').read_text());self.rows=[]
        assert self.ref['result']=='SEALED_V1_CERTIFIED_22_DAY_REFERENCE' and len(self.ref['days'])==22
        for p,h in self.ref['source_hashes'].items():assert self.e.stream.file_sha(p)==h,('PREFIX_BASELINE_DRIFT',p)
    def check_day(self,x,pending,day):
        if day>'2024-10-10':
            assert len(self.rows)==22,'PREFIX_NOT_CERTIFIED';return
        expected=self.ref['days'][len(self.rows)];assert day==expected['day']
        actual={}
        for family,attribute in DAILY.items():
            rows=[r for r in getattr(x,attribute) if r['day']==day]
            if family in ENRICH:rows=[dict(r,sector51=x.d.sid_sector[r['sid']]) if 'sid' in r else r for r in rows]
            actual[family]=digest(export_value(rows,self.e.frozen.clean if family in FUNDING else None))
        assert actual==expected['daily_hashes'],('PREFIX_DAILY_MISMATCH',day,[k for k in actual if actual[k]!=expected['daily_hashes'][k]])
        book=x.funding_book
        b=export_value(book_descriptor(book,[stream_hash(v,self.e.stream) for v in book['branches']]),self.e.frozen.clean)
        assert digest(b)==expected['book_descriptor_sha256'],('PREFIX_FULL_BRANCH_CONTENT_MISMATCH',day)
        if day=='2024-10-10':
            final={name:digest(export_value(getattr(x,attr),self.e.frozen.clean if name=='FUNDING_WAIT_STATE' else None)) for name,attr in FINAL.items()}
            final['PENDING_AT_END']=digest(export_value(pending,None))
            attempts=[]
            for a in x.archive.values():
                r={k:v for k,v in a.items() if k not in ['lots','cp','plan']};r['sector51']=x.d.sid_sector[a['sid']];r['final_qty']=x.quantity(a)
                r['marked_net_pnl']=str(a['cashflow']+a['dividend']+(x.qvalue(a,self.e.pd.Timestamp(day),'raw_close') if x.quantity(a) else self.e.D(0)));attempts.append(r)
            final['ATTEMPTS']=digest(export_value(attempts,None))
            assert final==self.ref['final_state_hashes'],('PREFIX_FINAL_STATE_MISMATCH',[k for k in final if final[k]!=self.ref['final_state_hashes'][k]])
            assert x.snapshots.get(('688200.SH','2024-10-10'))=={'q':0,'round':None},'EXACT_ADDED_ZERO_SNAPSHOT_ONLY'
        self.rows.append(dict(day=day,result='PASS',daily_families=len(actual),all_branch_content=True,selected_and_shadow_q_y=True))
