import unittest
import sys
import os

# إضافة المجلد الرئيسي للمشروع إلى مسار البحث لضمان العثور على ملفات accounts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import accounts

class TestAccounts(unittest.TestCase):

    def test_password_hash_and_check(self):
        # اختبار تشفير كلمة المرور والتحقق منها
        password = "123456"
        hashed = accounts.password_hash(password)
        
        # التأكد من أن كلمة المرور الصحيحة مقبولة
        self.assertTrue(accounts.check_password(password, hashed))
        
        # التأكد من أن كلمة المرور الخاطئة مرفوضة
        self.assertFalse(accounts.check_password("654321", hashed))

if __name__ == '__main__':
    unittest.main()
