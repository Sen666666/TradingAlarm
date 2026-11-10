"""Assemble verified main report and treatment-period supplement without modifying either."""
from pathlib import Path
import argparse,json,hashlib

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(p):
 a=p/'REPORT.md';b=p/'treatment_period_supplement/REPORT_SUPPLEMENT.md';out=p/'REPORT_COMPLETE.md'
 assert not out.exists()
 rm=json.loads((p/'REPORT_SOURCE_SHA256.json').read_text());sm=json.loads((b.parent/'OUTPUT_SHA256.json').read_text());assert sha(a)==rm['REPORT.md'] and sha(b)==sm[b.name]
 lead='重要：下列主报告全账户统计含继承前史；处理期全部新开round的独立分母、胜率、首BUY层及尾部身份比较见本报告后半部“处理期全部新开round补充”。一月固定cohort不因后继交易重算。\n\n'
 out.write_text(lead+a.read_text()+'\n\n'+b.read_text())
 (p/'REPORT_COMPLETE_SHA256.json').write_text(json.dumps({'REPORT_COMPLETE.md':sha(out),'main_report_SHA256':sha(a),'treatment_supplement_SHA256':sha(b),'assembler_SHA256':sha(Path(__file__))},indent=2))
 print(out)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,required=True);args=ap.parse_args();main(args.analysis)
