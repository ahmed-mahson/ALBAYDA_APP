import json
import threading
from pathlib import Path

# تحديد مسار مجلد البيانات وإنشائه إذا لم يكن موجوداً
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ACCOUNTS_FILE = DATA_DIR / "accounts.json"

_lock = threading.Lock()

def _default_data():
    return {"users": {}, "events": []}

def read():
    with _lock:
        if not ACCOUNTS_FILE.exists():
            return _default_data()
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            # إذا كان الملف تالفاً أو حدث خطأ، نرجع بيانات فارغة
            return _default_data()

def change(func):
    with _lock:
        data = read()
        result = func(data)
        
        # إذا كانت الدالة ترجع خطأ (مثل كلمة مرور خاطئة)، لا تحفظ التعديلات
        if isinstance(result, tuple) and len(result) == 2:
            user, error = result
            if error:
                return result
        
        # حفظ التعديلات في الملف بأمان
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return result
