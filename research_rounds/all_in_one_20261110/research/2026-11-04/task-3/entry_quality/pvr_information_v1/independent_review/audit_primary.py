"""Read-only original mother/PRIMARY identity and chronological-firstseen audit."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,hashlib,math,time
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;T=P.parent/'trend_exit_controls_v1';BIND={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p);BIND[str(p.resolve())]=sha(p)
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open())as f:return json.load(f)
def rows(p):
    p=Path(p);BIND[str(p.resolve())]=sha(p)
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open())as f:
        for line in f:yield json.loads(line)
def main():
    begun=time.monotonic();manifest=read(P/'universe_audit/PRIMARY_CANDIDATES_MANIFEST.json')
    assert sha(manifest['file'])==manifest['file_sha256']
    for p,h in manifest['source_sha256'].items():assert sha(p)==h
    old=read(P/'universe_audit/results_v1/UNIVERSE_COUNTS_AND_CLOCK_AUDIT.json');source={};findings={}
    for win in ['2022_2024','strong']:
        root=T/'runs/BASELINE'/win/'pair';b=read(root/'B.json.gz');intents={};dec={d['at'][:10]:d['at'] for d in b['decisions']}
        for d in b['decisions']:
            for i in d['intents']:
                k=d['at'][:10],i['sid'];assert i['cap']>0 and not i.get('size_reject')
                assert i['role'] not in intents.setdefault(k,{});intents[k][i['role']]=i
        ranks={(r['day'],r['sid']):r for r in rows(root/'rank-policy.jsonl.gz')};assert set(ranks)==set(intents)
        reserves=set();fills=set()
        for j in b['journal']:
            if j['kind']=='real_reserve':reserves.add((j['budget_order'].split('|')[1][:10],j['sid'],j['role']))
            elif j['kind']=='real_buy_fill':fills.add((j['signal_at'][:10],j['sid'],j['role']))
        c=Counter();perday=defaultdict(set);freekeys=set()
        for r in rows(root/'opportunities.jsonl.gz'):
            k=r['day'],r['sid'];assert r['sid'] not in perday[r['day']];perday[r['day']].add(r['sid']);c['full_grid']+=1
            free=bool(r['roles'])and not r['barriers']
            if r['roles']:c['raw_rows_with_roles']+=1
            if free:c['barrier_free']+=1;freekeys.add(k)
            if k in ranks:
                assert free and set(ranks[k]['roles'])<=set(r['roles'])
                if 'mobile' in intents[k]:assert intents[k]['mobile']['CP1_id']==r['CP1_id']
        assert set(perday)==set(dec) and all(len(ss)==1709 for ss in perday.values())
        assert c['full_grid']==1709*len(dec)
        assert c['barrier_free']==old[win]['mothers']['barrier_free_stock_days_with_roles']
        assert set(ranks)<=freekeys
        source[win]=(intents,ranks,reserves,fills,dec)
        findings[win]=dict(c,pending_stockdays=len(ranks),pending_role_rows=sum(map(len,intents.values())),actual_filled_intent_keys=len(fills))
    seen={};used=set();counts=defaultdict(Counter);event_counts=Counter();previous={}
    for r in rows(Path(manifest['file'])):
        win=r['window'];day=r['day'];sid=r['sid'];k=day,sid;intents,ranks,reserves,fills,dec=source[win]
        assert (win,day,sid)not in used;used.add((win,day,sid));assert previous.get(win,day)<=day;previous[win]=day
        rank=ranks[k];ii=intents[k];assert r['roles']==rank['roles'] and set(ii)==set(r['roles'])
        assert r['decision_at']==dec[day]
        for a,b in [('original_PVR','PVR'),('original_PVR_ready','PVR_ready'),('original_H1_rank','original_H1_rank'),('original_PVR_priority_rank','priority_rank'),('original_H1_slot','original_slot'),('original_PVR_slot','final_slot')]:assert r[a]==rank[b]
        core=ii.get('core');mobile=ii.get('mobile');ep=core['epoch'] if core else None;cp=mobile['CP1_id'] if mobile else None
        assert r['native_CORE_watch_epoch']==ep and r['canonical_CP1_receipt_id']==cp
        ck=json.dumps([win,sid,'core',ep],separators=(',',':'))if core and ep is not None else None
        mk=json.dumps([sid,'mobile',cp],separators=(',',':'))if mobile and cp is not None else None
        assert r['CORE_source_event_key']==ck and r['mobile_source_event_key']==mk
        unknown=[]
        if core and ck is None:unknown.append('CORE_native_epoch_missing')
        if mobile and mk is None:unknown.append('mobile_canonical_CP_missing')
        assert r['source_event_UNKNOWN_reasons']==unknown
        for role,key in [('CORE',ck),('mobile',mk)]:
            if key is None:assert r[role+'_event_firstseen_in_PRIMARY']is None and r[role+'_event_firstseen_day_in_PRIMARY']is None
            else:
                fresh=key not in seen
                if fresh:seen[key]=day;event_counts[win+'|'+role]+=1
                assert r[role+'_event_firstseen_in_PRIMARY']==fresh and r[role+'_event_firstseen_day_in_PRIMARY']==seen[key]
        for role in r['roles']:
            d=r['original_funding_diagnostic'][role];z=day,sid,role
            assert d['actual_reserved']==(z in reserves) and d['actual_filled']==(z in fills)
            assert d['right_censored_no_next_OPEN']==(day==max(dec))
        counts[win]['stock_days']+=1;counts[win]['role_rows']+=len(r['roles']);counts[win]['PVR_UNKNOWN']+=not r['original_PVR_ready'];counts[win]['source_event_UNKNOWN']+=bool(unknown)
    assert len(used)==133713 and dict(event_counts)==manifest['source_events_firstseen_counts']
    assert all(dict(counts[w])==manifest['windows'][w] for w in source)
    result=dict(status='PASS_ALL_PRIMARY_IDENTITIES_THREE_MOTHERS_ROLES_AND_PREFIX_FIRSTSEEN',findings=findings,primary_counts={w:dict(v)for w,v in counts.items()},source_events_firstseen_counts=dict(event_counts),source_sha256=BIND,script_sha256=sha(__file__),elapsed_seconds=time.monotonic()-begun,limits=['PRIMARY is original positive-size pending/rank stockdays before OPEN revalidation, not all fully executable orders or the same universe under a changed account.','CORE key is window-scoped original native watch epoch, not full-history canonical I identity. Firstseen only this PRIMARY chronological prefix; mobile canonical uniqueness does not imply independent trials.','Funding outcomes checked only as parallel original-path diagnostics; never used to filter PRIMARY or compute features.'],new_accounts=0,new_feature_exports=0,new_label_tables=0)
    (O/'PRIMARY_MOTHER_AND_EVENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['status'],findings,round(result['elapsed_seconds'],2),flush=True)
if __name__=='__main__':main()
