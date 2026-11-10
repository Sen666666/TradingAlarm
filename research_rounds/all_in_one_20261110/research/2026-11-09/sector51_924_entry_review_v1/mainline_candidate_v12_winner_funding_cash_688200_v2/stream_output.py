"""Lossless bounded-memory encoding of frozen M12 clean/save JSON, no account edits."""
from pathlib import Path
import gzip
import hashlib
import json
import numpy as np


def scalar(x):
    if isinstance(x, (bool, np.bool_)): return bool(x)
    if isinstance(x, (int, np.integer)): return int(x)
    if x is None or isinstance(x, (str, float)): return x
    return str(x)


def small_clean(x):
    # Only a set's own members require materialization for the frozen str sort.
    if isinstance(x, dict): return {str(k): small_clean(v) for k,v in sorted(x.items(),key=lambda p:str(p[0]))}
    if isinstance(x, (list,tuple)): return [small_clean(v) for v in x]
    if isinstance(x, set): return sorted((small_clean(v) for v in x),key=str)
    return scalar(x)


def json_chunks(value, level=0):
    """Exactly json.dumps(frozen.clean(value), ensure_ascii=False, indent=2, default=str).

    Dict key normalization/sorting is local; list values are traversed lazily.
    At most current object keys and a set's sorted members are copied, not a book/tree.
    Mirrors frozen clean's string-key collision behavior and insertion order.
    """
    if isinstance(value, dict):
        values = {str(k): v for k,v in sorted(value.items(),key=lambda p:str(p[0]))}
        if not values:
            yield '{}'; return
        yield '{\n'
        first=True
        for k,v in values.items():
            if not first: yield ',\n'
            first=False
            yield '  '*(level+1)
            yield json.dumps(k,ensure_ascii=False)
            yield ': '
            yield from json_chunks(v,level+1)
        yield '\n'+'  '*level+'}'
    elif isinstance(value,(list,tuple,set)):
        values = sorted((small_clean(v) for v in value),key=str) if isinstance(value,set) else value
        if not values:
            yield '[]'; return
        yield '[\n'
        first=True
        for v in values:
            if not first: yield ',\n'
            first=False
            yield '  '*(level+1)
            yield from json_chunks(v,level+1)
        yield '\n'+'  '*level+']'
    else:
        yield json.dumps(scalar(value),ensure_ascii=False,default=str)


def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def save_gzip(path,value):
    """Write exclusive deterministic gzip; decompression is byte-identical to old save."""
    path=Path(path);digest=hashlib.sha256();size=0;buffer=bytearray()
    with path.open('xb') as output:
        with gzip.GzipFile(filename='',fileobj=output,mode='wb',mtime=0,compresslevel=6) as gz:
            for part in json_chunks(value):
                buffer.extend(part.encode('utf-8'))
                if len(buffer)>=1024*1024:
                    digest.update(buffer);size+=len(buffer);gz.write(buffer);buffer.clear()
            buffer.extend(b'\n');digest.update(buffer);size+=len(buffer);gz.write(buffer)
    return dict(file=path.name,format='json+gzip',gzip_sha256=file_sha(path),gzip_bytes=path.stat().st_size,
                uncompressed_sha256=digest.hexdigest(),uncompressed_bytes=size,
                uncompressed_equivalence='BYTE_IDENTICAL_FROZEN_M12_CLEAN_THEN_SAVE',
                complete_fields=True,ordered_lists_preserved=True,numeric_semantics_unchanged=True)
