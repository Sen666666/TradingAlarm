"""Offline extraction of saved SZ southbound membership evidence; no network.

Outputs are research evidence CSV/JSON, not an executable eligibility feed.
Official announced_at and decision known_at remain null throughout.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl
import pdfplumber
from lxml import html
from pypdf import PdfReader

SOURCE = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/research_rounds/sector-stock-20261021/coverage')
OUT = Path(__file__).resolve().parent
INITIAL_DAY = '2016-12-05'
PILOT = ['00005', '00700', '01810', '02318', '09988']
MANUAL_CN = {'00005': '汇丰控股', '00700': '腾讯控股', '02318': '中国平安'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(name, data):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def save_csv(name, rows, fields=None):
    fields = fields or list(rows[0])
    with (OUT / name).open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    refs = {
        'initial_pdf': ('public-01-links02', 1),
        'initial_context': ('public-01-follow', 9),
        'adjustments_xlsx': ('public-01', 5),
    }
    sources = {}
    for key, (folder, sequence) in refs.items():
        report = json.loads((SOURCE / folder / 'results.json').read_text())
        row = next(r for r in report['requests'] if r['sequence'] == sequence)
        p = SOURCE / folder / row['response']
        assert sha(p) == row['sha256']
        sources[key] = {
            'source_id': key, 'path': str(p), 'url': row['url'],
            'sha256': sha(p), 'retrieved_at': row['requested_at'],
            'hosting_identity': 'SZSE official' if key == 'adjustments_xlsx' else 'CNFIN secondary reproduction attributed to SZSE',
        }

    context = html.fromstring(Path(sources['initial_context']['path']).read_bytes())
    for node in context.xpath('//script|//style'):
        node.drop_tree()
    context_text = ' '.join(context.text_content().split())
    assert '深交所网站2016年12月05日14:06' in context_text
    assert '自12月5日起生效' in context_text
    links = [x.get('href') for x in context.xpath('//a[@href]')]
    assert sources['initial_pdf']['url'] in links
    sources['initial_context'].update(
        display_publication_local='2016-12-05 14:06', display_timezone='not explicitly stated',
        official_announced_at=None, historical_known_at=None,
        effective_date_interpretation=INITIAL_DAY,
        effective_date_basis='Reproduced text says effective December 5; year from dated surrounding article.',
    )

    initial = []
    pdf_path = Path(sources['initial_pdf']['path'])
    pdf_texts = []
    with pdfplumber.open(pdf_path) as doc:
        for page_no, page in enumerate(doc.pages, 1):
            tables = page.extract_tables()
            assert len(tables) == 1, (page_no, len(tables))
            for table_row, cells in enumerate(tables[0], 1):
                if not cells[0] or not re.fullmatch(r'\d+', cells[0]):
                    continue
                ordinal = int(cells[0])
                code = cells[1].strip()
                assert re.fullmatch(r'\d{5}', code)
                initial.append(dict(
                    event_id=f'initial-{ordinal:03d}', source_id='initial_pdf',
                    source_sha256=sources['initial_pdf']['sha256'], source_page=page_no,
                    source_table_row=table_row, source_ordinal=ordinal,
                    code=code, symbol=f'{code}.HK', route='SZ_southbound',
                    name_en_extracted=' '.join((cells[3] or '').split()),
                    name_cn=MANUAL_CN.get(code),
                    name_cn_method='manual visual verification' if code in MANUAL_CN else 'not extracted: PDF CJK text mapping absent',
                    effective_date=INITIAL_DAY, effective_date_source='initial_context',
                    announced_at=None, known_at=None, event='initial_member',
                    secondary_host=True, eligible_for_account_input=False,
                ))
    assert [r['source_ordinal'] for r in initial] == list(range(1, 418))
    assert len({r['code'] for r in initial}) == 417
    reader = PdfReader(pdf_path)
    independent_codes = []
    for page_no, page in enumerate(reader.pages, 1):
        txt = page.extract_text()
        pdf_texts.append(dict(page=page_no, text=txt))
        independent_codes.extend((int(n), code) for n, code in re.findall(r'(?m)^\s*(\d+) (\d{5})(?=\s|$)', txt))
    assert independent_codes == [(r['source_ordinal'], r['code']) for r in initial]

    book = openpyxl.load_workbook(io.BytesIO(Path(sources['adjustments_xlsx']['path']).read_bytes()), data_only=True, read_only=True)
    sheet = book.active
    declared_dimension = sheet.calculate_dimension()
    # The source incorrectly declares A1; reset before streaming all physical rows.
    sheet.reset_dimensions()
    physical_rows = list(sheet.iter_rows(values_only=True))
    assert physical_rows[0] == ('证券代码', '中文简称', '英文简称', '调整内容', '调整生效日期')
    adjustments = []
    for source_row, cells in enumerate(physical_rows[1:], 2):
        code, cn, en, action, effective = cells
        code = str(code).zfill(5)
        assert re.fullmatch(r'\d{5}', code)
        assert action in ('调入', '调出')
        effective = str(effective)
        date.fromisoformat(effective)
        adjustments.append(dict(
            event_id=f'szse-xlsx-row-{source_row:04d}', source_id='adjustments_xlsx',
            source_sha256=sources['adjustments_xlsx']['sha256'],
            source_sheet=sheet.title, source_row=source_row, code=code, symbol=f'{code}.HK',
            route='SZ_southbound', name_cn=cn, name_en=en, action_raw=action,
            event='add' if action == '调入' else 'remove', effective_date=effective,
            announced_at=None, known_at=None, eligible_for_account_input=False,
        ))
    assert len(adjustments) == 1331
    assert len({r['event_id'] for r in adjustments}) == 1331
    # A retained source row number still resolves directly to the original XLSX.
    for row in adjustments:
        original = physical_rows[row['source_row'] - 1]
        assert (row['code'], row['action_raw'], row['effective_date']) == (str(original[0]).zfill(5), original[3], str(original[4]))

    initial_by_code = {r['code']: r for r in initial}
    all_codes = sorted(set(initial_by_code) | {r['code'] for r in adjustments})
    grouped = defaultdict(list)
    for row in adjustments:
        grouped[(row['code'], row['effective_date'])].append(row)
    observed_through = max(r['effective_date'] for r in adjustments)
    boundary = (date.fromisoformat(observed_through) + timedelta(days=1)).isoformat()
    intervals, anomalies = [], []

    def interval(code, start, end, state, source_events, warnings):
        if start >= end:
            return
        intervals.append(dict(
            code=code, symbol=f'{code}.HK', route='SZ_southbound',
            effective_from_inclusive=start, effective_to_exclusive=end,
            reconstructed_list_state=state,
            evidence_event_ids=';'.join(source_events),
            reconstruction_status='conditional_on_source_coverage_and_initial_list',
            continuity_warning=';'.join(warnings),
            announced_at=None, known_at=None,
            official_initial_host_verified=False,
            issuer_identity_verified=False,
            complete_southbound_union=False, executable_eligibility='unknown',
            eligible_for_account_input=False,
        ))

    for code in all_codes:
        state = 'listed' if code in initial_by_code else 'absent_from_initial_list'
        start = INITIAL_DAY
        source_events = [initial_by_code[code]['event_id']] if code in initial_by_code else ['initial-list-complete-assumption']
        warnings = []
        for key in sorted(k for k in grouped if k[0] == code):
            _, effective = key
            assert effective >= INITIAL_DAY
            rows = grouped[key]
            interval(code, start, effective, state, source_events, warnings)
            events = {r['event'] for r in rows}
            row_ids = [r['event_id'] for r in rows]
            this_warning = None
            if len(events) > 1:
                this_warning = 'same_code_same_day_conflicting_actions'
                next_state = 'unknown_conflict'
            else:
                event = next(iter(events))
                next_state = 'listed' if event == 'add' else 'removed_from_list'
                if event == 'add' and state == 'listed':
                    this_warning = 'add_while_already_listed'
                elif event == 'remove' and state in ('absent_from_initial_list', 'removed_from_list'):
                    this_warning = 'remove_while_not_listed'
                elif len(rows) > 1:
                    this_warning = 'duplicate_same_day_action'
            if this_warning:
                anomalies.append(dict(code=code, effective_date=effective, previous_state=state,
                                      action_set=';'.join(sorted(events)), issue=this_warning,
                                      event_ids=';'.join(row_ids), resolution='unresolved; no synthetic events inserted'))
                warnings.append(f'{effective}:{this_warning}')
            start, state, source_events = effective, next_state, row_ids
        interval(code, start, boundary, state, source_events, warnings)

    snapshots = []
    for code in PILOT:
        relevant = [r for r in intervals if r['code'] == code]
        for target in ['2015-01-05', INITIAL_DAY, '2020-01-02', '2026-10-20', observed_through]:
            found = [r for r in relevant if r['effective_from_inclusive'] <= target < r['effective_to_exclusive']]
            assert len(found) <= 1
            selected = found[0] if found else None
            snapshots.append(dict(code=code, symbol=f'{code}.HK', asof_date=target,
                                  initial_list_member=code in initial_by_code,
                                  initial_pdf_page=initial_by_code.get(code, {}).get('source_page'),
                                  reconstructed_list_state=selected['reconstructed_list_state'] if selected else 'unknown_outside_source_coverage',
                                  evidence_event_ids=selected['evidence_event_ids'] if selected else None,
                                  continuity_warning=selected['continuity_warning'] if selected else None,
                                  historical_known_at=None, executable_eligibility='unknown',
                                  complete_southbound_union=False))

    counts = Counter(r['issue'] for r in anomalies)
    summary = dict(
        created_at=datetime.now().astimezone().isoformat(), offline_only=True,
        source_pdfs=1, initial_pdf_pages=len(reader.pages), initial_members=len(initial),
        initial_extraction_methods_agree=True, initial_ordinals_complete=True,
        adjustments=len(adjustments), action_counts=dict(Counter(r['event'] for r in adjustments)),
        adjustment_effective_min=min(r['effective_date'] for r in adjustments),
        adjustment_effective_max=observed_through,
        unique_code_keys=len(all_codes), conditional_intervals=len(intervals),
        continuity_anomalies=len(anomalies), anomaly_counts=dict(counts),
        xlsx_declared_dimension=declared_dimension, actual_xlsx_rows_including_header=len(physical_rows),
        input_hashes_verified=True, adjustment_raw_row_checks=len(adjustments),
        reconstruction_start=INITIAL_DAY, reconstruction_end_exclusive=boundary,
        official_announced_at_populated=0, historical_known_at_populated=0,
        full_southbound_eligibility_established=False, economic_accounts_run=0,
        limitation='SZ-only historical list-state evidence, conditional on completeness and secondary initial list; not historically known or executable account eligibility.',
        builder_sha256=sha(Path(__file__)),
    )
    save_json('sources.json', sources)
    save_json('initial-page-texts.json', pdf_texts)
    save_csv('initial-members.csv', initial)
    save_csv('adjustments.csv', sorted(adjustments, key=lambda r: (r['effective_date'], r['code'], r['source_row'])))
    save_csv('conditional-list-state-intervals.csv', intervals)
    save_csv('continuity-anomalies.csv', anomalies, ['code','effective_date','previous_state','action_set','issue','event_ids','resolution'])
    save_csv('pilot-symbols.csv', snapshots)
    save_json('summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
