"""Saved-output exact v1 prefix comparison, no source-engine imports."""
from pathlib import Path
import copy,json,hashlib
from stream_branch_books import iter_books
END='2024-10-10'
DAILY=('ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','RETRY_TICKETS','INFORMATION_CONFIRMATIONS','TRANSFERS','FUNDING_REQUESTS','ADD_FLOOR_RISK','OPEN_SECTOR_EXPOSURE','AVAILABILITY_EVENTS','REFERENCE_DAILY','CAPITAL_LOTS','REFERENCE_REQUESTS','EVENT_LOG','EVENT_REQUEST_PLANS','SEED_FLOOR_RISK','SEED_COMMISSION_DIAGNOSTIC','FUNDING_OPEN_DECISIONS','FUNDING_WAIT_LOG','FUNDING_PREFLIGHT','FUNDING_ACTUAL_DIAGNOSTICS')
def read(p):return json.loads(Path(p).read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def daily_equal(old,new,end):
    days=[x['day'] for x in old['DAY_LEDGER'] if x['day']<=end]
    assert days==[x['day'] for x in new['DAY_LEDGER'] if x['day']<=end],'prefix_calendar'
    result=[]
    for day in days:
        hashes={}
        for family in DAILY:
            a=[x for x in old[family] if x['day']==day];b=[x for x in new[family] if x['day']==day]
            assert a==b,('v1_daily_difference',day,family)
            hashes[family]=digest(a)
        result.append(dict(day=day,families=len(hashes),hashes=hashes))
    return result

def descriptor(book):
    b={k:copy.deepcopy(v) for k,v in book.items() if k not in ('_stream_content_sha256','_max_raw_branch_chars','_context')}
    assert b['scratch_integrity']['passed'] is True and b['scratch_integrity']['before']==b['scratch_integrity']['after']
    assert book['_stream_content_sha256']==book['book_id'],'full_book_hash_invalid'
    if b['close_day']==END:
        b.pop('book_id');b['scratch_integrity']={'passed':True}
    return b

def branch_digest(b,i,prefix,context):return digest(b)

def compare_books(oldpath,newpath,end):
    old=iter_books(oldpath,branch_digest);new=iter_books(newpath,branch_digest);rows=[]
    for a in old:
        if a['close_day']>end:break
        b=next(new)
        assert a['close_day']==b['close_day']
        aa=descriptor(a);bb=descriptor(b)
        assert aa==bb,('v1_complete_book_difference',a['close_day'])
        rows.append(dict(day=a['close_day'],branches=len(a['branches']),canonical_descriptor_hash=digest(aa),allowed_non_economic_exclusion='Only book_id and scratch before/after on Oct10' if a['close_day']==END else None))
    return rows

def audit(oldpath,newpath,end):
    oldpath=Path(oldpath);newpath=Path(newpath);cutoff=min(end,END)
    old={n:read(oldpath/(n+'.json')) for n in DAILY};new={n:read(newpath/(n+'.json')) for n in DAILY}
    days=daily_equal(old,new,cutoff)
    books=compare_books(oldpath/'FUNDING_BRANCH_BOOKS.json',newpath/'FUNDING_BRANCH_BOOKS.json.gz',cutoff)
    assert [x['day'] for x in days]==[x['day'] for x in books]
    assert not [x for x in new['HOLDINGS'] if x['sid']=='688200.SH' and x['day']<='2024-10-10'],'nonzero_688200_record_holdings'
    assert not [x for x in new['ORDERS'] if x['sid']=='688200.SH' and x['day']<='2024-10-10'],'unexpected_688200_trade'
    return dict(verdict='PASS_INDEPENDENT_SAVED_V1_ECONOMIC_PREFIX',cutoff=cutoff,full_22_days_reached=cutoff==END,days=days,books=books,zero_record_position_688200=True,not_verified='Final tickets/active/archive in-memory state at Oct10 cannot be reconstructed solely from later final state. Bind runner checkpoint/prefix source review separately; no pickle loaded.')
