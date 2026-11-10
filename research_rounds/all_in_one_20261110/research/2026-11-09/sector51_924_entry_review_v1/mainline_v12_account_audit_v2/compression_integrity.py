"""Independent bounded-memory JSON gzip integrity. No candidate imports."""
from pathlib import Path
import gzip,hashlib,json

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def verify(path, manifest, output_hashes=None):
    path=Path(path)
    assert manifest['schema']=='LOSSLESS_JSON_GZIP_V1'
    matches=[x for x in manifest['files'] if x['file']==path.name]
    assert len(matches)==1
    m=matches[0];assert m['format']=='json+gzip' and path.name=='FUNDING_BRANCH_BOOKS.json.gz'
    assert path.stat().st_size==m['gzip_bytes'] and sha(path)==m['gzip_sha256'],'gzip_bytes_or_hash'
    if output_hashes is not None:assert output_hashes[path.name]==m['gzip_sha256'],'output_manifest_gzip_hash'
    assert m['uncompressed_equivalence']=='BYTE_IDENTICAL_FROZEN_M12_CLEAN_THEN_SAVE'
    assert all(m[k] is True for k in ('complete_fields','ordered_lists_preserved','numeric_semantics_unchanged'))
    h=hashlib.sha256();size=0
    with gzip.open(path,'rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):
            size+=len(part);assert size<=m['uncompressed_bytes'],'decompressed_length_overrun'
            h.update(part)
    assert size==m['uncompressed_bytes'] and h.hexdigest()==m['uncompressed_sha256'],'decompressed_bytes_or_hash'
    return dict(result='PASS_COMPRESSED_AND_DECOMPRESSED_BYTES',compressed_sha256=m['gzip_sha256'],compressed_bytes=m['gzip_bytes'],uncompressed_sha256=h.hexdigest(),uncompressed_bytes=size,manifest_claim_does_not_prove_semantics=True)
