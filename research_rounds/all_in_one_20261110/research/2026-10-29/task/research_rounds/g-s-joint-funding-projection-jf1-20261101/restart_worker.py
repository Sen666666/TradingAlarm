"""Cross-process certificate read, not an account runner."""
import sys,json
from pathlib import Path
from projector import CertificateBook
book=CertificateBook.loads(Path(sys.argv[1]).read_text())
ctx='same-industry-source-context'
Path(sys.argv[2]).write_text(json.dumps(dict(cap=book.cap(ctx,'NEW',999999,'2025-07-03 15:10:00+08:00'),orders=book.orders,filled=book.filled,financial_events=0),sort_keys=True)+'\n')
