"""Stream pretty-printed branch books one native branch at a time; no strategy import."""
from pathlib import Path
import hashlib,json,gzip
def encoded(x):return json.dumps(x,sort_keys=True,ensure_ascii=False).encode()
def indent(line):return len(line)-len(line.lstrip(' '))
def iter_books(path,inspect_branch):
    """Keep one raw branch and slim summaries, never the 7 GB array or whole raw book."""
    with (gzip.open(path, 'rt', encoding='utf-8') if str(path).endswith('.gz') else Path(path).open(encoding='utf-8')) as f:
        first=next(f);assert first.strip()=='['
        for line in f:
            if line.strip()==']':break
            if not line.strip():continue
            assert indent(line)==2 and line.strip()=='{',('book_start',line[:100])
            prefix=[line]
            for line in f:
                if indent(line)==4 and line.strip()=='"branches": [':break
                prefix.append(line)
            else:raise AssertionError('missing_branches')
            pd=json.loads(''.join(prefix).rstrip().removesuffix(',')+'}')
            assert all(k<'branches' for k in pd) and list(pd)==sorted(pd),'noncanonical_prefix_order'
            noid={k:v for k,v in pd.items() if k!='book_id'};h=hashlib.sha256()
            h.update(encoded(noid)[:-1]);h.update(b', "branches": [' if noid else b'"branches": [')
            summaries=[];context={};raw_max=0
            for line in f:
                if indent(line)==4 and line.strip() in ('],',']'):break
                assert indent(line)==6 and line.strip()=='{',('branch_start',line[:100])
                lines=[line]
                for line in f:
                    lines.append(line)
                    if indent(line)==6 and line.strip() in ('},','}'):break
                raw=''.join(lines).rstrip().removesuffix(',');raw_max=max(raw_max,len(raw))
                branch=json.loads(raw)
                if summaries:h.update(b', ')
                h.update(encoded(branch))
                summaries.append(inspect_branch(branch,len(summaries),pd,context))
                del lines,raw,branch
            else:raise AssertionError('missing_branches_end')
            h.update(b']');suffix=[]
            for line in f:
                suffix.append(line)
                if indent(line)==2 and line.strip() in ('},','}'):break
            else:raise AssertionError('missing_book_end')
            sd=json.loads('{'+''.join(suffix).rstrip().removesuffix(','))
            assert all(k>'branches' for k in sd) and list(sd)==sorted(sd),'noncanonical_suffix_order'
            if sd:h.update(b', ');h.update(encoded(sd)[1:])
            else:h.update(b'}')
            book=dict(pd,**sd,branches=summaries)
            book['_stream_content_sha256']=h.hexdigest();book['_max_raw_branch_chars']=raw_max;book['_context']=context
            yield book
