document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const errorBox = document.getElementById('error-message');
    const loginBtn = document.getElementById('login-btn');

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // منع إعادة تحميل الصفحة
            
            // إخفاء رسالة الخطأ السابقة وتعطيل الزر
            errorBox.style.display = 'none';
            loginBtn.textContent = 'جاري الدخول...';
            loginBtn.disabled = true;

            const identity = document.getElementById('identity').value.trim();
            const password = document.getElementById('password').value.trim();

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ identity: identity, password: password })
                });

                const data = await response.json();

                if (response.ok) {
                    // نجاح الدخول
                    window.location.href = '/'; // الانتقال للشاشة الرئيسية
                } else {
                    // فشل الدخول (إظهار رسالة الخطأ من الخادم)
                    throw new Error(data.error || 'بيانات الدخول غير صحيحة.');
                }
            } catch (error) {
                // إظهار الخطأ للمستخدم
                errorBox.textContent = error.message;
                errorBox.style.display = 'block';
                loginBtn.textContent = 'دخول';
                loginBtn.disabled = false;
            }
        });
    }
});
