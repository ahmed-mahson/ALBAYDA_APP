package ai.teable.albayda.court.preview;

import ai.teable.albayda.court.preview.CredentialVault;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.util.Base64;
import android.view.View;
import android.view.ViewTreeObserver;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebMessage;
import android.webkit.WebMessagePort;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import org.json.JSONObject;

/* loaded from: classes.dex */
public class MainActivity extends Activity {
    private static final String APP_TITLE = "تقنية معلومات محكمة البيضاء الابتدائية";
    private String appUrl;
    private static final int NAVY = Color.rgb(3, 29, 64);
    private static final int PICK_FILE = 101;
    private static final int SAVE_FILE = 102;
    private String bridgeScript;
    private LinearLayout errorPanel;
    private TextView errorText;
    private boolean failed;
    private ValueCallback<Uri[]> fileCallback;
    private WebMessagePort nativePort;
    private byte[] pendingFile;
    private ProgressBar progress;
    private CredentialVault vault;
    private WebView web;

    private int dp(int i) {
        return (int) ((i * getResources().getDisplayMetrics().density) + 0.5f);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public boolean trusted(String str) {
        if (str == null) {
            return false;
        }
        Uri uri = Uri.parse(str);
        return "https".equalsIgnoreCase(uri.getScheme()) && !appUrl.isEmpty() && Uri.parse(appUrl).getHost().equalsIgnoreCase(uri.getHost()) && Uri.parse(appUrl).getPort() == uri.getPort();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void toast(String str) {
        Toast.makeText(this, str, 1).show();
    }

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        this.appUrl = getPreferences(MODE_PRIVATE).getString("server", BuildConfig.APP_URL);
        getWindow().setStatusBarColor(NAVY);
        getWindow().setNavigationBarColor(NAVY);
        getWindow().setSoftInputMode(16);
        final LinearLayout linearLayout = new LinearLayout(this);
        linearLayout.setOrientation(1);
        linearLayout.setBackgroundColor(NAVY);
        linearLayout.setLayoutDirection(1);
        linearLayout.setFitsSystemWindows(true);
        this.progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        this.progress.setMax(100);
        linearLayout.addView(this.progress, new LinearLayout.LayoutParams(-1, dp(3)));
        FrameLayout frameLayout = new FrameLayout(this);
        linearLayout.addView(frameLayout, new LinearLayout.LayoutParams(-1, 0, 1.0f));
        this.web = new WebView(this);
        this.web.setBackgroundColor(NAVY);
        this.vault = new CredentialVault(this, new CredentialVault.Sender() { // from class: ai.teable.albayda.court.preview.MainActivity$$ExternalSyntheticLambda1
            @Override // ai.teable.albayda.court.preview.CredentialVault.Sender
            public final void send(JSONObject jSONObject) {
                MainActivity.this.m8lambda$onCreate$0$aiteablealbaydacourtpreviewMainActivity(jSONObject);
            }
        });
        frameLayout.addView(this.web, new FrameLayout.LayoutParams(-1, -1));
        this.errorPanel = new LinearLayout(this);
        this.errorPanel.setOrientation(1);
        this.errorPanel.setGravity(17);
        this.errorPanel.setPadding(dp(28), dp(24), dp(28), dp(24));
        this.errorPanel.setBackgroundColor(NAVY);
        this.errorText = new TextView(this);
        this.errorText.setTextSize(17.0f);
        this.errorText.setTextColor(-1);
        this.errorText.setGravity(17);
        this.errorPanel.addView(this.errorText);
        android.widget.EditText serverInput = new android.widget.EditText(this);
        serverInput.setSingleLine(true);
        serverInput.setTextColor(Color.WHITE);
        serverInput.setHintTextColor(Color.LTGRAY);
        serverInput.setTextDirection(View.TEXT_DIRECTION_LTR);
        serverInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        serverInput.setHint("https://court.example.org/");
        serverInput.setText(appUrl);
        this.errorPanel.addView(serverInput, new LinearLayout.LayoutParams(-1, -2));
        Button saveServer = new Button(this);
        saveServer.setText("حفظ الرابط وفتح التطبيق");
        saveServer.setOnClickListener(v -> {
            String value = serverInput.getText().toString().trim();
            try {
                java.net.URI parsed = new java.net.URI(value);
                if (!"https".equals(parsed.getScheme()) || parsed.getHost() == null || parsed.getUserInfo() != null || parsed.getQuery() != null || parsed.getFragment() != null || !(parsed.getPath().isEmpty() || "/".equals(parsed.getPath()))) throw new IllegalArgumentException();
                String normalized = value.endsWith("/") ? value : value + "/";
                if (!normalized.equals(appUrl)) { vault.clearSaved(); CookieManager.getInstance().removeAllCookies(null); }
                appUrl = normalized;
                getPreferences(MODE_PRIVATE).edit().putString("server", appUrl).apply();
                errorPanel.setVisibility(View.GONE);
                web.loadUrl(appUrl);
            } catch (Exception error) { serverInput.setError("أدخل رابط HTTPS صحيحًا أو أكمل عملية البصمة الحالية أولًا."); }
        });
        this.errorPanel.addView(saveServer);
        Button button = new Button(this);
        button.setText("إعادة المحاولة");
        button.setOnClickListener(new View.OnClickListener() { // from class: ai.teable.albayda.court.preview.MainActivity$$ExternalSyntheticLambda2
            @Override // android.view.View.OnClickListener
            public final void onClick(View view) {
                MainActivity.this.m9lambda$onCreate$1$aiteablealbaydacourtpreviewMainActivity(view);
            }
        });
        LinearLayout.LayoutParams layoutParams = new LinearLayout.LayoutParams(-2, -2);
        layoutParams.topMargin = dp(24);
        this.errorPanel.addView(button, layoutParams);
        frameLayout.addView(this.errorPanel, new FrameLayout.LayoutParams(-1, -1));
        this.errorPanel.setVisibility(8);
        setContentView(linearLayout);
        linearLayout.post(this::enterFullscreen);
        if (Build.VERSION.SDK_INT < 30) {
            linearLayout.getViewTreeObserver().addOnGlobalLayoutListener(new ViewTreeObserver.OnGlobalLayoutListener() { // from class: ai.teable.albayda.court.preview.MainActivity$$ExternalSyntheticLambda3
                @Override // android.view.ViewTreeObserver.OnGlobalLayoutListener
                public final void onGlobalLayout() {
                    MainActivity.lambda$onCreate$2(linearLayout);
                }
            });
        }
        try {
            InputStream inputStreamOpen = getAssets().open("android.js");
            try {
                ByteArrayOutputStream byteArrayOutputStream = new ByteArrayOutputStream();
                byte[] bArr = new byte[4096];
                while (true) {
                    int i = inputStreamOpen.read(bArr);
                    if (i == -1) {
                        break;
                    } else {
                        byteArrayOutputStream.write(bArr, 0, i);
                    }
                }
                this.bridgeScript = byteArrayOutputStream.toString("UTF-8");
                if (inputStreamOpen != null) {
                    inputStreamOpen.close();
                }
            } finally {
            }
        } catch (Exception e) {
            this.bridgeScript = "";
        }
        WebSettings settings = this.web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setUserAgentString(settings.getUserAgentString() + " AlBaydaCourtAndroid/3.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(this.web, false);
        WebView.setWebContentsDebuggingEnabled(false);
        this.web.setWebViewClient(new WebViewClient() { // from class: ai.teable.albayda.court.preview.MainActivity.1
            @Override // android.webkit.WebViewClient
            public boolean shouldOverrideUrlLoading(WebView webView, WebResourceRequest webResourceRequest) {
                if (webResourceRequest.isForMainFrame()) {
                    return MainActivity.this.route(webResourceRequest.getUrl());
                }
                return false;
            }

            @Override // android.webkit.WebViewClient
            public boolean shouldOverrideUrlLoading(WebView webView, String str) {
                return MainActivity.this.route(Uri.parse(str));
            }

            @Override // android.webkit.WebViewClient
            public void onPageStarted(WebView webView, String str, Bitmap bitmap) {
                MainActivity.this.failed = false;
                MainActivity.this.errorPanel.setVisibility(8);
                MainActivity.this.progress.setVisibility(0);
                MainActivity.this.closePort();
            }

            @Override // android.webkit.WebViewClient
            public void onPageCommitVisible(WebView webView, String str) {
                if (!MainActivity.this.failed && MainActivity.this.trusted(str) && MainActivity.this.nativePort == null) {
                    MainActivity.this.connectBridge();
                }
            }

            @Override // android.webkit.WebViewClient
            public void onPageFinished(WebView webView, String str) {
                MainActivity.this.progress.setVisibility(8);
                CookieManager.getInstance().flush();
                if (!MainActivity.this.failed && MainActivity.this.trusted(str) && MainActivity.this.nativePort == null) {
                    MainActivity.this.connectBridge();
                }
            }

            @Override // android.webkit.WebViewClient
            public void onReceivedError(WebView webView, WebResourceRequest webResourceRequest, WebResourceError webResourceError) {
                if (webResourceRequest.isForMainFrame()) {
                    MainActivity.this.showError("تعذر الاتصال بالتطبيق. تحقق من الإنترنت ثم أعد المحاولة.");
                }
            }

            @Override // android.webkit.WebViewClient
            public void onReceivedHttpError(WebView webView, WebResourceRequest webResourceRequest, WebResourceResponse webResourceResponse) {
                if (webResourceRequest.isForMainFrame() && webResourceResponse.getStatusCode() >= 400) {
                    MainActivity.this.showError("الخادم غير متاح حاليًا. أعد المحاولة بعد قليل.");
                }
            }
        });
        this.web.setWebChromeClient(new WebChromeClient() { // from class: ai.teable.albayda.court.preview.MainActivity.2
            @Override // android.webkit.WebChromeClient
            public void onProgressChanged(WebView webView, int i2) {
                MainActivity.this.progress.setProgress(i2);
            }

            @Override // android.webkit.WebChromeClient
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> valueCallback, WebChromeClient.FileChooserParams fileChooserParams) {
                if (!MainActivity.this.trusted(MainActivity.this.web.getUrl())) {
                    return false;
                }
                if (MainActivity.this.fileCallback != null) {
                    MainActivity.this.fileCallback.onReceiveValue(null);
                }
                MainActivity.this.fileCallback = valueCallback;
                try {
                    MainActivity.this.startActivityForResult(fileChooserParams.createIntent(), MainActivity.PICK_FILE);
                    return true;
                } catch (ActivityNotFoundException e2) {
                    MainActivity.this.fileCallback.onReceiveValue(null);
                    MainActivity.this.fileCallback = null;
                    MainActivity.this.toast("لا يوجد تطبيق لاختيار الملفات.");
                    return true;
                }
            }
        });
        this.web.setDownloadListener(new DownloadListener() { // from class: ai.teable.albayda.court.preview.MainActivity$$ExternalSyntheticLambda4
            @Override // android.webkit.DownloadListener
            public final void onDownloadStart(String str, String str2, String str3, String str4, long j) {
                MainActivity.this.m10lambda$onCreate$3$aiteablealbaydacourtpreviewMainActivity(str, str2, str3, str4, j);
            }
        });
        if (appUrl.isEmpty()) {
            showError("أدخل رابط خادم التطبيق لتفعيل خدمات البحث.");
        } else if (bundle == null || this.web.restoreState(bundle) == null) {
            this.web.loadUrl(appUrl);
        }
    }

    /* renamed from: lambda$onCreate$0$ai-teable-albayda-court-preview-MainActivity, reason: not valid java name */
    /* synthetic */ void m8lambda$onCreate$0$aiteablealbaydacourtpreviewMainActivity(JSONObject jSONObject) {
        if (this.nativePort != null && trusted(this.web.getUrl())) {
            JSONObject jSONObjectOptJSONObject = jSONObject.optJSONObject("payload");
            if (jSONObjectOptJSONObject == null || !jSONObjectOptJSONObject.has("password") || "/login".equals(Uri.parse(this.web.getUrl()).getPath())) {
                this.nativePort.postMessage(new WebMessage(jSONObject.toString()));
            }
        }
    }

    /* renamed from: lambda$onCreate$1$ai-teable-albayda-court-preview-MainActivity, reason: not valid java name */
    /* synthetic */ void m9lambda$onCreate$1$aiteablealbaydacourtpreviewMainActivity(View view) {
        this.errorPanel.setVisibility(8);
        this.web.loadUrl(appUrl);
    }

    static /* synthetic */ void lambda$onCreate$2(LinearLayout linearLayout) {
        Rect rect = new Rect();
        linearLayout.getWindowVisibleDisplayFrame(rect);
        int height = linearLayout.getRootView().getHeight();
        int iMax = Math.max(0, height - rect.bottom);
        if (iMax <= height / 5) {
            iMax = 0;
        }
        if (linearLayout.getPaddingBottom() != iMax) {
            linearLayout.setPadding(0, 0, 0, iMax);
        }
    }

    /* renamed from: lambda$onCreate$3$ai-teable-albayda-court-preview-MainActivity, reason: not valid java name */
    /* synthetic */ void m10lambda$onCreate$3$aiteablealbaydacourtpreviewMainActivity(String str, String str2, String str3, String str4, long j) {
        download(str, str2, str3, str4);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public boolean route(Uri uri) {
        if (trusted(uri.toString())) {
            return false;
        }
        String scheme = uri.getScheme();
        if ("https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme) || "tel".equalsIgnoreCase(scheme) || "mailto".equalsIgnoreCase(scheme) || "whatsapp".equalsIgnoreCase(scheme) || "tg".equalsIgnoreCase(scheme)) {
            try {
                startActivity(new Intent("android.intent.action.VIEW", uri).addCategory("android.intent.category.BROWSABLE"));
                return true;
            } catch (ActivityNotFoundException e) {
                toast("لا يوجد تطبيق مناسب لفتح الرابط.");
                return true;
            }
        }
        return true;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void showError(String str) {
        this.failed = true;
        this.progress.setVisibility(8);
        this.errorText.setText(str);
        this.errorPanel.setVisibility(0);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void closePort() {
        if (this.nativePort != null) {
            this.nativePort.close();
            this.nativePort = null;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void connectBridge() {
        closePort();
        this.web.evaluateJavascript(this.bridgeScript, new ValueCallback() { // from class: ai.teable.albayda.court.preview.MainActivity$$ExternalSyntheticLambda0
            @Override // android.webkit.ValueCallback
            public final void onReceiveValue(Object obj) {
                MainActivity.this.m7x3fa586cb((String) obj);
            }
        });
    }

    /* renamed from: lambda$connectBridge$4$ai-teable-albayda-court-preview-MainActivity, reason: not valid java name */
    /* synthetic */ void m7x3fa586cb(String str) {
        if (trusted(this.web.getUrl())) {
            WebMessagePort[] webMessagePortArrCreateWebMessageChannel = this.web.createWebMessageChannel();
            this.nativePort = webMessagePortArrCreateWebMessageChannel[0];
            this.nativePort.setWebMessageCallback(new WebMessagePort.WebMessageCallback() { // from class: ai.teable.albayda.court.preview.MainActivity.3
                @Override // android.webkit.WebMessagePort.WebMessageCallback
                public void onMessage(WebMessagePort webMessagePort, WebMessage webMessage) {
                    if (MainActivity.this.trusted(MainActivity.this.web.getUrl())) {
                        try {
                            String data = webMessage.getData();
                            if (data == null || data.length() > 47185920) {
                                throw new IllegalArgumentException();
                            }
                            JSONObject jSONObject = new JSONObject(data);
                            String strOptString = jSONObject.optString("action");
                            if (strOptString.startsWith("credential-")) {
                                if ("credential-status".equals(strOptString) || "credential-forget".equals(strOptString) || "/login".equals(Uri.parse(MainActivity.this.web.getUrl()).getPath())) {
                                    MainActivity.this.vault.handle(jSONObject);
                                }
                            } else if ("print".equals(strOptString)) {
                                MainActivity.this.printPage();
                            } else if ("close".equals(strOptString)) {
                                if (MainActivity.this.web.canGoBack()) {
                                    MainActivity.this.web.goBack();
                                } else {
                                    MainActivity.this.web.loadUrl(MainActivity.this.appUrl);
                                }
                            } else if ("save".equals(strOptString)) {
                                MainActivity.this.saveFile(jSONObject);
                            } else if ("error".equals(strOptString)) {
                                MainActivity.this.toast("تعذر تجهيز الملف للتنزيل. حاول مرة أخرى أو افتح التطبيق في المتصفح.");
                            }
                        } catch (Exception e) {
                            MainActivity.this.toast("تعذر تجهيز الملف.");
                        }
                    }
                }
            });
            this.web.postWebMessage(new WebMessage("court-android-init", new WebMessagePort[]{webMessagePortArrCreateWebMessageChannel[1]}), Uri.parse(appUrl));
            this.vault.announce();
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void saveFile(JSONObject jSONObject) throws Exception {
        if (this.pendingFile != null) {
            toast("أكمل حفظ الملف السابق أولًا.");
            return;
        }
        String string = jSONObject.getString("data");
        int iIndexOf = string.indexOf(44);
        if (iIndexOf < 0 || !string.substring(0, iIndexOf).contains(";base64")) {
            throw new IllegalArgumentException();
        }
        this.pendingFile = Base64.decode(string.substring(iIndexOf + 1), 0);
        String strReplaceAll = jSONObject.optString("name", "document").replaceAll("[\\\\/\\p{Cntrl}]", "_");
        if (strReplaceAll.length() > 160) {
            strReplaceAll = strReplaceAll.substring(strReplaceAll.length() - 160);
        }
        String strOptString = jSONObject.optString("mime", "application/octet-stream");
        try {
            startActivityForResult(new Intent("android.intent.action.CREATE_DOCUMENT").addCategory("android.intent.category.OPENABLE").setType(strOptString.isEmpty() ? "application/octet-stream" : strOptString).putExtra("android.intent.extra.TITLE", strReplaceAll), SAVE_FILE);
        } catch (ActivityNotFoundException e) {
            this.pendingFile = null;
            toast("لا يوجد تطبيق لحفظ الملفات.");
        }
    }

    private void download(String str, String str2, String str3, String str4) {
        if (!trusted(str)) {
            toast("افتح الرابط في المتصفح لتنزيل هذا الملف.");
            return;
        }
        try {
            String strGuessFileName = URLUtil.guessFileName(str, str3, str4);
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(str));
            request.setTitle(strGuessFileName).setMimeType(str4).setNotificationVisibility(1);
            String cookie = CookieManager.getInstance().getCookie(str);
            if (cookie != null) {
                request.addRequestHeader("Cookie", cookie);
            }
            if (str2 != null) {
                request.addRequestHeader("User-Agent", str2);
            }
            if (Build.VERSION.SDK_INT >= 29) {
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, strGuessFileName);
            } else {
                request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, strGuessFileName);
            }
            ((DownloadManager) getSystemService("download")).enqueue(request);
            toast("بدأ تنزيل الملف.");
        } catch (Exception e) {
            toast("تعذر تنزيل الملف. أعد المحاولة.");
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void printPage() {
        if (trusted(this.web.getUrl())) {
            ((PrintManager) getSystemService("print")).print(APP_TITLE, this.web.createPrintDocumentAdapter("AlBayda-Court"), new PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build());
        }
    }

    private void enterFullscreen() {
        // getDecorView initializes PhoneWindow's decor; getInsetsController alone does not.
        View decor = getWindow().getDecorView();
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController insetsController = decor.getWindowInsetsController();
            if (insetsController != null) {
                insetsController.setSystemBarsBehavior(2);
                insetsController.hide(WindowInsets.Type.systemBars());
                return;
            }
            return;
        }
        decor.setSystemUiVisibility(4358);
    }

    @Override // android.app.Activity, android.view.Window.Callback
    public void onWindowFocusChanged(boolean z) {
        super.onWindowFocusChanged(z);
        if (z) {
            enterFullscreen();
        }
    }

    @Override // android.app.Activity
    protected void onResume() {
        super.onResume();
        enterFullscreen();
    }

    @Override // android.app.Activity
    protected void onActivityResult(int i, int i2, Intent intent) {
        super.onActivityResult(i, i2, intent);
        if (i == PICK_FILE && this.fileCallback != null) {
            this.fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(i2, intent));
            this.fileCallback = null;
            return;
        }
        if (i == SAVE_FILE) {
            byte[] bArr = this.pendingFile;
            this.pendingFile = null;
            if (i2 == -1 && intent != null && intent.getData() != null && bArr != null) {
                try {
                    OutputStream outputStreamOpenOutputStream = getContentResolver().openOutputStream(intent.getData());
                    try {
                        if (outputStreamOpenOutputStream == null) {
                            throw new IOException();
                        }
                        outputStreamOpenOutputStream.write(bArr);
                        toast("تم حفظ الملف.");
                        if (outputStreamOpenOutputStream != null) {
                            outputStreamOpenOutputStream.close();
                        }
                    } finally {
                    }
                } catch (Exception e) {
                    toast("تعذر حفظ الملف.");
                }
            }
        }
    }

    @Override // android.app.Activity
    protected void onSaveInstanceState(Bundle bundle) {
        super.onSaveInstanceState(bundle);
        this.web.saveState(bundle);
    }

    @Override // android.app.Activity
    public void onBackPressed() {
        if (this.web.canGoBack()) {
            this.web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override // android.app.Activity
    protected void onPause() {
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override // android.app.Activity
    protected void onDestroy() {
        this.vault.destroy();
        closePort();
        if (this.fileCallback != null) {
            this.fileCallback.onReceiveValue(null);
        }
        this.web.destroy();
        super.onDestroy();
    }
}
