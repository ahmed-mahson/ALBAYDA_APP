import csv
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from pypdf import PdfReader
import app
import case_records as c

RECORD = {'الجلسة السابقة':'2026/11/01','الجلسة القادمة':'2026/11/15','حالة القضية':'تأجيل للاطلاع','برئاسة القاضي':'قاضي تجريبي','المدعى عليه':'طرف تجريبي ثان','المدعي':'طرف تجريبي أول','تاريخ ورودها':'2026/01/02','موضوعها':'بيانات اختبار فقط','نوع القضية':'مدنية','رقم القضية':'12/1448'}

def request(path, payload=None, cookie='', **extra):
    body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else b''
    environ={'PATH_INFO':path,'REQUEST_METHOD':'POST' if payload is not None else 'GET','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),'HTTP_COOKIE':cookie,'wsgi.url_scheme':'https','REMOTE_ADDR':'test',**extra}
    result={}
    def start(status, headers): result.update(status=int(status.split()[0]),headers=dict(headers))
    result['body']=b''.join(app.application(environ,start))
    return result

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'APP_REQUIRE_AUTH':'false','COURT_MULTIUSER':'false'});self.env.start()
        self.records=patch.object(c,'load_case_records',return_value=[dict(RECORD)]);self.records.start()
    def tearDown(self): self.records.stop();self.env.stop()
    def test_static_files(self):
        for path in ['/','/login','/app.js','/style.css','/assets/albayda-it-logo.webp','/assets/sultan-medium.ttf','/healthz']:
            with self.subTest(path=path): self.assertEqual(request(path)['status'],200)
    def test_static_traversal(self):
        for path in ['/../app.py','/%2e%2e/app.py','/assets/../app.py','/assets/templates/case-info.pdf']:
            with self.subTest(path=path): self.assertEqual(request(path)['status'],404)
    def test_search_contract(self):
        result=request('/api/cases/search',{'query':'١٤٤٨/١٢','method':'number'})
        data=json.loads(result['body']);self.assertEqual(data['count'],1);self.assertEqual(data['results'][0],RECORD)
    def test_name_filters_and_limit(self):
        self.assertEqual(len(c.search_case_records([RECORD]*8,'تجريبي','name')),5)
        self.assertEqual(c.search_case_records([RECORD],'تجريبي','name',case_type='شخصية'),[])
        self.assertEqual(c.search_case_records([RECORD],'تجريبي','name',judge='آخر'),[])
    def test_options(self):
        data=json.loads(request('/api/cases/options',{})['body']);self.assertEqual(data['case_types'],['مدنيــــة']);self.assertEqual(data['judges'],['قاضي تجريبي'])
    def test_sessions(self):
        data=json.loads(request('/api/sessions/search',{'date':'٢٠٢٦/١١/١٥'})['body']);self.assertEqual(data['date'],'2026-11-15');self.assertEqual(data['count'],1)
    def test_invalid_input(self):
        for path,payload in [('/api/cases/search',{'query':''}),('/api/sessions/search',{'date':'bad'}),('/api/supreme-court/search',{})]:
            with self.subTest(path=path): self.assertEqual(request(path,payload)['status'],400)
    def test_source_failure(self):
        with patch.object(c,'load_case_records',side_effect=c.CaseRecordsError('تعذر الوصول')):
            self.assertEqual(request('/api/cases/search',{'query':'test'})['status'],503)
    def test_exact_record_after_partial_match(self):
        partial={**RECORD,'رقم القضية':'112/1448'}
        with patch.object(c,'load_case_records',return_value=[partial]*101+[RECORD]):
            response=request('/api/cases/report',{'case_number':'١٤٤٨/١٢'})
            self.assertEqual(response['status'],200)
            self.assertTrue(response['body'].startswith(b'%PDF'))
    def test_attendance_after_partial_match(self):
        partial={**RECORD,'رقم القضية':'112/1448'}
        payload={'case_number':'1448/12','case_type':'مدنيــــة','judge_filter':'قاضي تجريبي','judge':'قاضي تجريبي','plaintiff':'طرف أول','defendant':'طرف ثان','session_date':'2026-11-15'}
        with patch.object(c,'load_case_records',return_value=[partial,RECORD]):
            self.assertEqual(request('/api/attendance-ad',payload)['status'],200)
    def test_pdf_routes(self):
        for path,payload in [('/api/cases/report',{'case_number':'12/1448'}),('/api/sessions/pdf',{'date':'2026-11-15'})]:
            with self.subTest(path=path):
                response=request(path,payload);self.assertEqual(response['status'],200);self.assertEqual(response['headers']['Content-Type'],'application/pdf');self.assertEqual(len(PdfReader(io.BytesIO(response['body'])).pages),1)
    def test_supreme_contract(self):
        rows=[('الطاعن / الملتمس','طرف أول'),('المطعون / الملتمس ضده','طرف ثان'),('نوع القضية','طعن'),('تاريخ الاستلام','2026/01/02'),('الرقم الخاص بخدمة الرسائل القصيرة','123'),('تاريخ الإرسال','2026/11/01')]
        with patch.object(c,'search_supreme_court_cases',return_value=rows):
            data=json.loads(request('/api/supreme-court/search',{'name':'طرف'})['body']);self.assertEqual(data['count'],1);self.assertEqual(len(data['results'][0]),6)
            response=request('/api/supreme-court/report',{'name':'طرف'});self.assertEqual(response['status'],200);self.assertEqual(len(PdfReader(io.BytesIO(response['body'])).pages),1)
    def test_arabic_password(self):
        with patch.dict(os.environ,{'APP_REQUIRE_AUTH':'true','APP_ACCESS_PASSWORD':'كلمة مرور تجريبية طويلة','APP_SESSION_SECRET':'x'*40}):
            app.validate_configuration()
            self.assertEqual(request('/api/cases/options',{})['status'],401)
            self.assertEqual(request('/')['status'],303)
            response=request('/api/login',{'password':'كلمة مرور تجريبية طويلة'})
            self.assertEqual(response['status'],200);cookie=response['headers']['Set-Cookie'];self.assertIn('Secure',cookie)
            self.assertEqual(request('/api/cases/options',{},cookie=cookie)['status'],200)
            self.assertEqual(request('/api/login',{'password':'خاطئة'})['status'],401)
    def test_malformed_cookie(self):
        with patch.dict(os.environ,{'APP_REQUIRE_AUTH':'true','APP_SESSION_SECRET':'x'*40}):
            for value in ['١٢.abc','9'*500+'.abc','123.عربي','123.'+'a'*64]:
                self.assertEqual(request('/api/cases/options',{},cookie='albayda_session='+value)['status'],401)
    def test_production_configuration(self):
        with patch.dict(os.environ,{'APP_REQUIRE_AUTH':'true','APP_ACCESS_PASSWORD':'','APP_SESSION_SECRET':''}):
            with self.assertRaises(RuntimeError): app.validate_configuration()
    def test_csv_mapping(self):
        values=['']*27
        values[1]='نوع القضية الأساسي';values[8]='برئاسة القاضي';values[14]='رقم القضية'
        for index,key in [(16,'الجلسة السابقة'),(17,'الجلسة القادمة'),(19,'حالة القضية'),(20,'برئاسة القاضي'),(21,'المدعى عليه'),(22,'المدعي'),(23,'تاريخ ورودها'),(24,'موضوعها'),(25,'نوع القضية'),(26,'رقم القضية')]:values[index]=RECORD[key]
        inner=io.StringIO();csv.writer(inner).writerow(values)
        outer=io.StringIO();csv.writer(outer).writerow([inner.getvalue().strip()])
        self.assertEqual(c._parse_case_records(outer.getvalue().encode()),[RECORD])

class SourceStorageTests(unittest.TestCase):
    def test_local_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sercase.csv';path.write_bytes(b'local-source')
            with patch.dict(os.environ,{'CASE_RECORDS_LOCAL_FILE':str(path)}):
                self.assertEqual(c._read_case_source(),b'local-source')
            with patch.dict(os.environ,{'CASE_RECORDS_LOCAL_FILE':str(path)+'-missing'}):
                with self.assertRaises(c.CaseRecordsError): c._read_case_source()
    def test_atomic_snapshot_and_default_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'private'/'sercase.csv'
            with patch.dict(os.environ,{'CASE_RECORDS_SNAPSHOT_PATH':str(path)}):
                c._save_case_snapshot(b'first');c._save_case_snapshot(b'second')
                self.assertEqual(path.read_bytes(),b'second')
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with patch.dict(os.environ,{'CASE_RECORDS_LOCAL_FILE':''}),patch.object(c,'_download_case_csv',return_value=b'drive'):
                self.assertEqual(c._read_case_source(),b'drive')

if __name__=='__main__': unittest.main()
