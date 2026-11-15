package ai.teable.albayda.court.preview;

import android.annotation.SuppressLint;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.Toast;
import android.widget.FrameLayout;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // إنشاء حاوية (Layout) لاحتواء الويب فيو وشريط التحميل
        FrameLayout layout = new FrameLayout(this);
        
        // 1. إعداد WebView
        webView = new WebView(this);
        layout.addView(webView);

        // 2. إعداد شريط التحميل (ProgressBar)
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleLarge);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
        );
        params.gravity = android.view.Gravity.CENTER;
        progressBar.setLayoutParams(params);
        layout.addView(progressBar);

        setContentView(layout);

        WebSettings webSettings = webView.getSettings();

        // --- إعدادات أساسية هامة ---
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);
        webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        
        // تحسين الأداء
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        // --- مراقبة حالة التحميل والأخطاء ---
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

        // =====================================================================
        // 🛑 هام جداً: استبدل الرابط التالي برابط موقعك الفعلي على Render
        // =====================================================================
        String appUrl = "https://your-app-name.onrender.com"; // <--- ضع رابطك هنا
        
        webView.loadUrl(appUrl);
    }

    // التعامل مع زر الرجوع في الهاتف
    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
