"""Component restore against separately supplied trusted fixture views; no account."""
import sys,json,hashlib
from pathlib import Path
from projector import CertificateBook
trusted_path=Path(sys.argv[2])
if hashlib.sha256(trusted_path.read_bytes()).hexdigest()!=sys.argv[3]:raise ValueError('trusted fixture boundary changed')
trusted=json.loads(trusted_path.read_text())
b=CertificateBook.loads(Path(sys.argv[1]).read_text(),**trusted)
Path(sys.argv[4]).write_text(json.dumps(dict(cap=b.cap('same-industry-source-context','NEW',999999,'2025-07-03 15:10:00+08:00',receipt_id='receipt-NEW'),orders=b.orders,filled=b.filled,financial_events=0),sort_keys=True)+'\n')
