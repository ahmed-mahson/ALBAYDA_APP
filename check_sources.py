from pathlib import Path
import json
import case_records as c

report = {}
try:
    data = c._download_case_csv()
    records = c._parse_case_records(data)
    report['google_drive'] = {'ok': True, 'records': len(records), 'case_types': c.available_case_types(records)}
except c.CaseRecordsError as exc:
    report['google_drive'] = {'ok': False, 'error': str(exc)}
try:
    html = c._fetch_supreme_court_html('https://ysc.org.ye/')
    Path('/tmp/supreme-home.html').write_text(html)
    report['supreme_court'] = {'ok': True, 'bytes': len(html.encode())}
except c.CaseRecordsError as exc:
    report['supreme_court'] = {'ok': False, 'error': str(exc)}
Path('/tmp/source-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
