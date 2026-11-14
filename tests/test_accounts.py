import io,json,os,unittest
from unittest.mock import patch
import app,accounts
class AccountsTests(unittest.TestCase):
    def setUp(self):
        self.data={'users':{'admin':{'id':'admin','name':'Test Admin','phone':'771000000','hash':accounts.password_hash('12345678'),'role':'admin','status':'active','created':'2026-01-01','version':1,'failures':0,'locked_until':0}},'events':[]}
        self.patches=[patch.dict(os.environ,{'COURT_MULTIUSER':'true','APP_SESSION_SECRET':'s'*48}),patch('account_store.read',side_effect=lambda:self.data),patch('account_store.change',side_effect=lambda f:f(self.data))]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        app._login_attempts.clear()
    def request(self,path,data=None,cookie=''):
        raw=json.dumps(data or {}).encode();out=[]
        env={'PATH_INFO':path,'REQUEST_METHOD':'POST' if data is not None else 'GET','wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json','HTTP_COOKIE':cookie,'wsgi.url_scheme':'https','REMOTE_ADDR':'test'}
        body=b''.join(app.application(env,lambda s,h:out.extend([int(s.split()[0]),dict(h)])))
        return out[0],json.loads(body) if body else {},out[1]
    def login(self,identity,password):
        status,data,headers=self.request('/api/login',{'identity':identity,'password':password})
        return status,headers.get('Set-Cookie','').split(';')[0]
    def test_approval_authorization_and_revocation(self):
        self.assertEqual(self.request('/api/register',{'name':'Test User','phone':'772000000','password':'123456','confirm':'123456'})[0],201)
        uid=next(k for k in self.data['users'] if k!='admin')
        self.assertEqual(self.login('772000000','123456')[0],403)
        self.assertEqual(self.request('/api/admin/users')[0],401)
        status,admin=self.login('Test Admin','12345678');self.assertEqual(status,200)
        self.assertEqual(self.request('/api/admin/status',{'id':uid,'status':'active'},admin)[0],200)
        status,user=self.login('Test User','123456');self.assertEqual(status,200)
        self.assertEqual(self.request('/api/admin/users',cookie=user)[0],403)
        self.assertEqual(self.request('/api/me',cookie=user)[0],200)
        self.assertEqual(self.request('/api/admin/status',{'id':uid,'status':'disabled'},admin)[0],200)
        self.assertEqual(self.request('/api/me',cookie=user)[0],401)
        self.assertNotIn('hash',self.request('/api/admin/users',cookie=admin)[1]['users'][0])
    def test_password_and_duplicate_validation(self):
        for pw in ('12345','abcdef'):
            self.assertEqual(self.request('/api/register',{'name':'Test User','phone':'772000000','password':pw,'confirm':pw})[0],400)
        self.assertEqual(self.request('/api/register',{'name':'Test User','phone':'772000000','password':'123456','confirm':'123457'})[0],400)
        self.assertEqual(self.request('/api/register',{'name':'New Admin','phone':'771000000','password':'123456','confirm':'123456'})[0],400)
    def test_logout_and_admin_self_disable(self):
        status,c=self.login('771000000','12345678');self.assertEqual(status,200)
        self.assertEqual(self.request('/api/admin/status',{'id':'admin','status':'disabled'},c)[0],400)
        self.assertEqual(self.request('/api/logout',{},c)[0],200)
        self.assertEqual(self.request('/api/me',cookie=c)[0],401)
    def test_store_failure_fails_closed(self):
        _,c=self.login('771000000','12345678')
        with patch('account_store.read',side_effect=RuntimeError('offline')):
            self.assertEqual(self.request('/api/me',cookie=c)[0],503)
    def test_tampered_cookie_rejected(self):
        _,c=self.login('771000000','12345678')
        self.assertEqual(self.request('/api/me',cookie=c[:-1]+'x')[0],401)
