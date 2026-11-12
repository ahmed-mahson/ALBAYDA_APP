package ye.court.albayda

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import android.net.http.SslError
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private val fileWriter = Executors.newSingleThreadExecutor()
    private val appUri by lazy { Uri.parse(BuildConfig.APP_BASE_URL) }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
        }
        webView.addJavascriptInterface(DownloadBridge(), "AlbaydaAndroid")
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean {
                val destination = request.url
                if (destination.scheme == "https" && destination.host == appUri.host) {
                    return false
                }
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, destination))
                    true
                } catch (_: Exception) {
                    true
                }
            }

            override fun onReceivedSslError(
                view: WebView,
                handler: SslErrorHandler,
                error: SslError,
            ) {
                handler.cancel()
                notifyUser("تعذر التحقق من شهادة أمان الخادم.")
            }
        }
        setContentView(webView)
        webView.loadUrl(BuildConfig.APP_BASE_URL)
    }

    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        if (::webView.isInitialized) {
            webView.removeJavascriptInterface("AlbaydaAndroid")
            webView.destroy()
        }
        fileWriter.shutdown()
        super.onDestroy()
    }

    private fun notifyUser(message: String) {
        runOnUiThread {
            Toast.makeText(this, message, Toast.LENGTH_LONG).show()
        }
    }

    private inner class DownloadBridge {
        @JavascriptInterface
        fun saveFile(filename: String, mimeType: String, base64Content: String) {
            fileWriter.execute {
                val safeName = filename.substringAfterLast('/')
                    .replace(Regex("[^\\p{L}\\p{N}._-]"), "_")
                    .ifBlank { "court-document.pdf" }
                val values = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, safeName)
                    put(MediaStore.Downloads.MIME_TYPE, mimeType.ifBlank { "application/pdf" })
                    put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val destination = contentResolver.insert(
                    MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                    values,
                )
                if (destination == null) {
                    notifyUser("تعذر حفظ الملف في مجلد التنزيلات.")
                    return@execute
                }
                try {
                    val content = Base64.decode(base64Content, Base64.DEFAULT)
                    contentResolver.openOutputStream(destination)?.use { output ->
                        output.write(content)
                    } ?: throw IllegalStateException("تعذر فتح ملف التنزيل.")
                    contentResolver.update(
                        destination,
                        ContentValues().apply {
                            put(MediaStore.Downloads.IS_PENDING, 0)
                        },
                        null,
                        null,
                    )
                    notifyUser("تم حفظ الملف في مجلد التنزيلات.")
                } catch (_: Exception) {
                    contentResolver.delete(destination, null, null)
                    notifyUser("تعذر حفظ الملف. حاول تنزيله مرة أخرى.")
                }
            }
        }
    }
}
