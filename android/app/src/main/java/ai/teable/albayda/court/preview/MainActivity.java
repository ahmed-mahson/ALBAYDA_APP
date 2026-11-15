package ai.teable.albayda.court.preview;

import android.annotation.SuppressLint;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. تغيير لون شريط الحالة العلوي (الوقت والبطارية) ليطابق لون التطبيق الأزرق الداكن
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(Color.parseColor("#0A192F"));
        }

        // 2. إنشاء الحاوية الرئيسية (Layout) لاحتواء الويب فيو وشريط التحميل
        FrameLayout layout = new FrameLayout(this);
        
        webView = new WebView(this);
        layout.addView(webView);

        // 3. إعداد شريط التحميل (يظهر في المنتصف أثناء جلب الصفحة)
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleLarge);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
        );
        params.gravity = android.view.Gravity.CENTER;
        progressBar.setLayoutParams(params);
        layout.addView(progressBar);

        setContentView(layout);

        // 4. إعدادات WebView
        WebSettings webSettings = webView.getSettings();

        // --- الإعدادات الأساسية ---
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);
        
        // --- الإعدادات الخاصة بجعل التطبيق يبدو كتطبيق أصلي (Native) ---
        // إجبار التطبيق على عرض الصفحة بعرض شاشة الهاتف بالضبط (حل مشكلة كبر الصورة)
        webSettings.setUseWideViewPort(true);
        webSettings.setLoadWithOverviewMode(true);
        
        // منع المستخدم من التكبير والتصغير بإصبعيه (ليبدو كتطبيق وليس متصفح)
        webSettings.setSupportZoom(false);
        webSettings.setBuiltInZoomControls(false);
        webSettings.setDisplayZoomControls(false);
        
        // السماح بالمحتوى المختلط (إذا كان الموقع يستخدم http داخل https)
        webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        // 5. مراقبة حالة التحميل والأخطاء
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                progressBar.setVisibility(View.VISIBLE); // إظهار شريط التحميل
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                progressBar.setVisibility(View.GONE); // إخفاء شريط التحميل عند الانتهاء
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                progressBar.setVisibility(View.GONE);
                Toast.makeText(MainActivity.this, "تعذر الاتصال بالخادم. تأكد من الإنترنت.", Toast.LENGTH_LONG).show();
            }
        });

        // 6. مسح الكاش القديم لضمان تحميل أحدث نسخة من الموقع
        webView.clearCache(true);

        // =====================================================================
        // 🛑 ضع رابط موقعك الفعلي هنا (تأكد أنه يبدأ بـ https)
        // =====================================================================
        String appUrl = "https://albayda-court.onrender.com"; 
        
        webView.loadUrl(appUrl);
    }

    // 7. التعامل مع زر الرجوع في الهاتف (للعودة داخل الصفحات وليس إغلاق التطبيق مباشرة)
    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
