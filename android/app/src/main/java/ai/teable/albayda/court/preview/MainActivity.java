package ai.teable.albayda.court.preview;

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

        // 1. تفعيل الجافا سكريبت
        webSettings.setJavaScriptEnabled(true);

        // 2. تفعيل التخزين المحلي (DOM Storage)
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);

        // 3. السماح بقراءة الملفات المحلية من داخل الـ APK
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);

        // 4. إعدادات الكاش (بديل setAppCacheEnabled القديم)
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);

        // 5. تحسين الأداء (Hardware Acceleration)
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        // 6. منع فتح الروابط في المتصفح الخارجي (يبقى داخل التطبيق)
        webView.setWebViewClient(new WebViewClient());

        // 7. تحميل رابط التطبيق (افترض أن خادم Python يعمل محلياً على المنفذ 8080)
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
