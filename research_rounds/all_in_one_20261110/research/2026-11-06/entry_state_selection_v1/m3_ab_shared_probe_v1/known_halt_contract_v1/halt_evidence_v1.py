"""Explicit-session adjudicated official disclosures. Never infer halts from missing bars."""
from pathlib import Path
from datetime import datetime, time
from zoneinfo import ZoneInfo
import hashlib,json
TZ=ZoneInfo('Asia/Shanghai')
class HaltEvidence:
    def __init__(self,rows=(),*,synthetic=False):
        self.rows=tuple(rows);self.synthetic=synthetic;self.hashes={}
        seen=set()
        for r in self.rows:
            key=(r['sid'],r['session'])
            if key in seen:raise ValueError('Duplicate/conflicting session evidence')
            seen.add(key)
            if not synthetic:
                if r.get('adjudication')!='OFFICIAL_DISCLOSURE_WITH_PREOPEN_PUBLICATION_CLOCK':raise ValueError('Unadmitted official evidence')
                for a in r['artifacts']:
                    p=Path(a['path']);h=hashlib.sha256(p.read_bytes()).hexdigest()
                    if h!=a['sha256']:raise ValueError('Evidence changed: '+str(p))
                    self.hashes[str(p)]=h
                if not r.get('official_url') or not r.get('clock_url') or len(r['artifacts'])<2:raise ValueError('Missing content or clock provenance')
    def get(self,sid,day):
        session=str(day.date())
        for r in self.rows:
            if r['sid']!=sid or r['session']!=session or r.get('scope')!='FULL_DAY':continue
            try:
                known=datetime.fromisoformat(r['known_at'])
                if known.tzinfo is None:continue
                cutoff=datetime.combine(day.date(),time(9,30),TZ)
                if known.astimezone(TZ)>=cutoff:continue
            except (KeyError,TypeError,ValueError):continue
            return r
        return None
    @classmethod
    def load(cls,path):
        path=Path(path);obj=cls(json.loads(path.read_text())['sessions'])
        obj.hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest();return obj
