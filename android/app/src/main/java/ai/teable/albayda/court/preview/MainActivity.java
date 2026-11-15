package com.example.albayda; // تأكد من تغيير اسم الحزمة

import android.annotation.SuppressLint;
import android.os.Bundle;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        webView = new WebView(this);
        setContentView(webView);

        WebSettings webSettings = webView.getSettings();

        // تفعيل الجافا سكريبت
        webSettings.setJavaScriptEnabled(true);

        // تفعيل التخزين المحلي والكاش
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setAppCacheEnabled(true);

        // السماح بقراءة الملفات
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);

        // تحسين الأداء
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        // منع فتح المتصفح الخارجي
        webView.setWebViewClient(new WebViewClient());

        // تحميل الرابط (رابط الخادم المحلي)
        webView.loadUrl("http://127.0.0.1:8080");
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
