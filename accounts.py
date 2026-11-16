import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus as H
from http.cookies import SimpleCookie

import account_store as store

COOKIE = 'court_user'

def digits(v):
    return str(v).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest

def check_password(password, hashed):
    return hmac.compare_digest(password_hash(password, hashed.split(':')[0]), hashed)

def public(u):
    return {k: u[k] for k in ('id', 'name', 'phone', 'role', 'status', 'created')}

def event(d, user, action, result='success'):
    d['events'].append({
        'id': uuid.uuid4().hex,
        'time': datetime.now(timezone.utc).isoformat(),
        'user': user,
        'action': action,
        'result': result
    })

def token(u):
    raw = base64.urlsafe_b64encode(json.dumps([u['id'], u['version'], int(time.time())]).encode()).decode().rstrip('=')
    return raw + '.' + hmac.new(os.environ.get('APP_SESSION_SECRET', 'default_secret_key_for_dev').encode(), raw.encode(), hashlib.sha256).hexdigest()

def current(env):
    try:
        c = SimpleCookie()
        c.load(env.get('HTTP_COOKIE', ''))
        raw, sig = c[COOKIE].value.split('.')
        expected = hmac.new(os.environ.get('APP_SESSION_SECRET', 'default_secret_key_for_dev').encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        uid, version, issued = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
        if not 0 <= time.time() - issued < 43200:
            return None
    except (ValueError, KeyError, TypeError):
        return None
    u = store.read()['users'].get(uid)
    return u if u and u['status'] == 'active' and u['version'] == version else None

def handle(app, original, env, start):
    path = env.get('PATH_INFO', '/')
    method = env.get('REQUEST_METHOD', 'GET')
    response = lambda status, data, headers=(): app._json_response(start, status, data, headers)
    assets = {'/style.css', '/login.js', '/welcome.js', '/assets/app-icon-transparent.png', '/assets/sultan-medium.ttf', '/register.html'}
    
    if path == '/healthz':
        return original(env, start)
    if method == 'GET' and path in assets:
        return app._static_file(path, start)
        
    try:
        if path == '/api/register' and method == 'POST':
            if app._login_is_limited('register:' + env.get('REMOTE_ADDR', '')):
                return response(H.TOO_MANY_REQUESTS, {'error': 'حاول لاحقًا.'})
                
            p = app._read_json(env)
            name = str(p.get('name', '')).strip()
            phone = digits(p.get('phone', '')).strip()
            pw = digits(p.get('password', ''))
            
            if not 3 <= len(name) <= 60 or not re.fullmatch(r'[0-9]{9,15}', phone):
                raise ValueError('أدخل اسمًا من 3 أحرف ورقم هاتف صحيحًا.')
                
            # شرط كلمة المرور: من 6 إلى 9 أرقام
            if not re.fullmatch(r'[0-9]{6,9}', pw) or pw != digits(p.get('confirm', '')):
                raise ValueError('كلمة المرور أرقام فقط، من 6 إلى 9 أرقام، ويجب تطابق التأكيد.')
                
            hashed = password_hash(pw)
            
            def register(d):
                if any(u['phone'] == phone or u['name'].casefold() == name.casefold() for u in d['users'].values()):
                    raise ValueError('الاسم أو رقم الهاتف مستخدم بالفعل.')
                uid = uuid.uuid4().hex
                
                # جعل رقم هاتفك هو المسؤول الوحيد (Admin) تلقائياً
                is_admin = (phone == '734840710')
                role = 'admin' if is_admin else 'user'
                status = 'active' if is_admin else 'pending'
                
                d['users'][uid] = {
                    'id': uid,
                    'name': name,
                    'phone': phone,
                    'hash': hashed,
                    'role': role,
                    'status': status,
                    'created': datetime.now(timezone.utc).isoformat(),
                    'version': 1,
                    'failures': 0,
                    'locked_until': 0
                }
                event(d, uid, 'register', 'pending')
                
            store.change(register)
            return response(H.CREATED, {'message': 'تم إرسال طلب الحساب. انتظر موافقة مسؤول النظام.'})
            
        if path == '/api/login' and method == 'POST':
            if app._login_is_limited('login:' + env.get('REMOTE_ADDR', '')):
                return response(H.TOO_MANY_REQUESTS, {'error': 'تجاوزت المحاولات المسموحة. حاول بعد دقيقة.'})
                
            p = app._read_json(env)
            identity = digits(p.get('identity', '')).strip()
            pw = digits(p.get('password', ''))
            
            found = next((u for u in store.read()['users'].values() if identity == u['phone'] or identity.casefold() == u['name'].casefold()), None)
            if not found:
                return response(H.UNAUTHORIZED, {'error': 'بيانات الدخول غير صحيحة.'})
                
            def login(d):
                u = d['users'][found['id']]
                if u.get('locked_until', 0) > time.time():
                    event(d, u['id'], 'login', 'locked')
                    return None, 'الحساب مقفل مؤقتًا. حاول بعد 15 دقيقة.'
                if not check_password(pw, u['hash']):
                    u['failures'] = u.get('failures', 0) + 1
                    if u['failures'] >= 5:
                        u['locked_until'] = int(time.time()) + 900
                        u['failures'] = 0
                    event(d, u['id'], 'login', 'failed')
                    return None, 'بيانات الدخول غير صحيحة.'
                if u['status'] != 'active':
                    event(d, u['id'], 'login', u['status'])
                    return None, 'حسابك بانتظار الموافقة أو غير مفعل. تواصل مع المسؤول.'
                u['failures'] = 0
                u['locked_until'] = 0
                event(d, u['id'], 'login')
                return u, None
                
            user, error = store.change(login)
            if error:
                return response(H.FORBIDDEN, {'error': error})
                
            cookie = f'{COOKIE}={token(user)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200'
            if app._secure_request(env):
                cookie += '; Secure'
            return response(H.OK, {'authenticated': True, 'user': public(user)}, [('Set-Cookie', cookie)])
            
        user = current(env)
        if path == '/login' and method == 'GET':
            return app._redirect_response(start, '/') if user else app._static_file('/login.html', start)
            
        if not user:
            return response(H.UNAUTHORIZED, {'error': 'سجّل الدخول أولًا.'}) if path.startswith('/api/') else app._redirect_response(start, '/login')
            
        if path == '/api/me' and method == 'GET':
            return response(H.OK, {'user': public(user)})
            
        if path == '/api/logout' and method == 'POST':
            def logout(d):
                d['users'][user['id']]['version'] += 1
                event(d, user['id'], 'logout')
            store.change(logout)
            return response(H.OK, {'authenticated': False}, [('Set-Cookie', COOKIE + '=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0')])
            
        if path.startswith('/api/admin/'):
            if user['role'] != 'admin':
                return response(H.FORBIDDEN, {'error': 'هذه الخدمة لمسؤول النظام فقط.'})
            if path == '/api/admin/users' and method == 'GET':
                d = store.read()
                return response(H.OK, {'users': [public(u) for u in d['users'].values()], 'events': d['events'][-200:][::-1]})
            if path == '/api/admin/status' and method == 'POST':
                p = app._read_json(env)
                if p.get('status') not in ('active', 'rejected', 'disabled'):
                    raise ValueError('حالة غير صالحة.')
                def update(d):
                    target = d['users'].get(p.get('id'))
                    if not target or target['role'] == 'admin':
                        raise ValueError('لا يمكن تعديل حساب المسؤول من هذه العملية.')
                    target['status'] = p['status']
                    target['version'] += 1
                    event(d, user['id'], 'account:' + target['id'], p['status'])
                store.change(update)
                return response(H.OK, {'updated': True})
            return response(H.NOT_FOUND, {'error': 'غير موجود.'})
            
        env['court.authenticated'] = True
        if path in ('/api/cases/report', '/api/sessions/pdf', '/api/attendance-ad', '/api/supreme-court/report') and method == 'POST':
            captured = []
            def capture(status, headers):
                captured.extend([status, headers])
            result = original(env, capture)
            if captured[0].startswith('200'):
                store.change(lambda d: event(d, user['id'], 'report:' + path))
            start(*captured)
            return result
            
        return original(env, start)
        
    except ValueError as e:
        return response(H.BAD_REQUEST, {'error': str(e)})
    except Exception as e:
        app.LOGGER.exception('Account service unavailable')
        # إظهار الخطأ الحقيقي بدلاً من الرسالة العامة
        return response(H.SERVICE_UNAVAILABLE, {'error': f'حدث خطأ في الخادم: {str(e)}'})
