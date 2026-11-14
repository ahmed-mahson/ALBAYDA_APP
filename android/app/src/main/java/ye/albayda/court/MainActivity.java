package ye.albayda.court;

import android.app.Activity;
import android.os.Bundle;
import android.net.Uri;
import android.content.Intent;
import android.content.ContentValues;
import android.provider.MediaStore;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.JavascriptInterface;
import android.webkit.CookieManager;
import android.util.Base64;
import android.widget.Toast;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.EditText;
import android.widget.Button;
import android.widget.ImageView;
import java.io.OutputStream;
import java.io.ByteArrayInputStream;

public class MainActivity extends Activity {
    private WebView web;
    private volatile Uri origin;
    private boolean sameOrigin(Uri uri) {
        return origin != null && "https".equals(uri.getScheme()) && origin.getHost().equals(uri.getHost()) && origin.getPort() == uri.getPort();
    }
    private String savedUrl() { return getPreferences(MODE_PRIVATE).getString("server", BuildConfig.APP_URL); }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (savedUrl().isEmpty()) showSettings(); else openServer(savedUrl());
    }
    private void showSettings() {
        if (web != null) { web.destroy(); web = null; }
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setLayoutDirection(android.view.View.LAYOUT_DIRECTION_RTL);
        int pad = (int)(24 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, pad);
        ImageView logo = new ImageView(this);
        logo.setImageResource(ye.albayda.court.R.mipmap.ic_launcher);
        layout.addView(logo, new LinearLayout.LayoutParams(-1, pad * 6));
        TextView title = new TextView(this);
        title.setText("تقنية معلومات محكمة البيضاء الابتدائية\nإعداد خادم التطبيق");
        title.setTextSize(24); layout.addView(title);
        TextView help = new TextView(this);
        help.setText("أدخل رابط HTTPS للخادم الذي يشغّل app.py. تُجلب القضايا والجلسات من المصدر المعتمد عبر هذا الخادم. لن تعمل خدمات البحث قبل ربط خادم متاح.");
        help.setTextSize(17); layout.addView(help);
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        input.setTextDirection(android.view.View.TEXT_DIRECTION_LTR);
        input.setHint("https://court.example.org/"); input.setText(savedUrl()); layout.addView(input);
        Button connect = new Button(this); connect.setText("حفظ الرابط وفتح التطبيق"); layout.addView(connect);
        connect.setOnClickListener(view -> {
            String value = input.getText().toString().trim();
            try {
                java.net.URI parsed = new java.net.URI(value);
                if (!"https".equals(parsed.getScheme()) || parsed.getHost() == null || parsed.getUserInfo() != null || parsed.getQuery() != null || parsed.getFragment() != null || !(parsed.getPath().isEmpty() || "/".equals(parsed.getPath()))) throw new IllegalArgumentException();
                String normalized = value.endsWith("/") ? value : value + "/";
                if (!normalized.equals(savedUrl())) { CookieManager.getInstance().removeAllCookies(null); CookieManager.getInstance().flush(); }
                getPreferences(MODE_PRIVATE).edit().putString("server", normalized).apply(); openServer(normalized);
            } catch (Exception error) { input.setError("أدخل رابط HTTPS صحيحًا دون مسار فرعي أو بيانات دخول."); }
        });
        setContentView(layout);
    }
    private void openServer(String url) {
        origin = Uri.parse(url);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        Button settings = new Button(this); settings.setText("إعداد رابط الخادم"); settings.setOnClickListener(v -> showSettings()); layout.addView(settings);
        web = new WebView(this); layout.addView(web, new LinearLayout.LayoutParams(-1, 0, 1)); setContentView(layout);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.addJavascriptInterface(new PdfDownload(), "CourtAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (sameOrigin(request.getUrl())) return false;
                String scheme = request.getUrl().getScheme();
                if ("https".equals(scheme) || "mailto".equals(scheme) || "tel".equals(scheme)) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); } catch (Exception ignored) { }
                }
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (sameOrigin(request.getUrl())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
        });
        web.loadUrl(url);
    }
    public class PdfDownload {
        @JavascriptInterface public void savePdf(String data, String filename) {
            Uri saved = null;
            try {
                if (data.length() > 45000000) throw new IllegalArgumentException();
                byte[] bytes = Base64.decode(data, Base64.DEFAULT);
                if (bytes.length < 5 || bytes[0] != '%' || bytes[1] != 'P' || bytes[2] != 'D' || bytes[3] != 'F') throw new IllegalArgumentException();
                ContentValues values = new ContentValues();
                values.put(MediaStore.Downloads.DISPLAY_NAME, filename.replaceAll("[/\\\\]", "_").replaceAll("[\\r\\n]", "_"));
                values.put(MediaStore.Downloads.MIME_TYPE, "application/pdf");
                values.put(MediaStore.Downloads.IS_PENDING, 1);
                saved = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (saved == null) throw new IllegalStateException();
                try (OutputStream out = getContentResolver().openOutputStream(saved)) { out.write(bytes); }
                values.clear(); values.put(MediaStore.Downloads.IS_PENDING, 0);
                getContentResolver().update(saved, values, null, null);
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "تم حفظ PDF في التنزيلات", Toast.LENGTH_LONG).show());
            } catch (Exception error) {
                if (saved != null) getContentResolver().delete(saved, null, null);
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "تعذر حفظ الملف", Toast.LENGTH_LONG).show());
            }
        }
    }
    @Override public void onBackPressed() { if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onPause() { CookieManager.getInstance().flush(); super.onPause(); }
    @Override protected void onDestroy() { if (web != null) web.destroy(); super.onDestroy(); }
}
