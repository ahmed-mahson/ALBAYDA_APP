const CACHE_NAME = 'albayda-cache-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    '/style.css',
    '/app.js',
    '/welcome.js',
    '/assets/app-icon-transparent.png',
    '/assets/sultan-medium.ttf', // ضع اسم الخط الخاص بك هنا
    // أضف أي صور أو أيقونات أخرى تريد حفظها هنا
];

// تثبيت وتخزين الملفات
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

// جلب الملفات من الذاكرة عند انقطاع الإنترنت
self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            // إذا وجد الملف في الذاكرة، استخدمه. وإلا، اطلبه من الإنترنت
            return response || fetch(event.request);
        })
    );
});

// تحديث الذاكرة عند تغيير الإصدار
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
});
