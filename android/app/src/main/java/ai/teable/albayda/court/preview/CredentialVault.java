package ai.teable.albayda.court.preview;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.hardware.fingerprint.FingerprintManager;
import android.os.Build;
import android.os.CancellationSignal;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyPermanentlyInvalidatedException;
import android.util.Base64;
import java.security.InvalidAlgorithmParameterException;
import java.security.InvalidKeyException;
import java.security.KeyStore;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.NoSuchPaddingException;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONObject;

/* loaded from: classes.dex */
final class CredentialVault {
    private static final String BASIC_KEY = "albayda.credentials.device.v1";
    private static final String BIO_KEY = "albayda.credentials.biometric.v1";
    private AlertDialog activeDialog;
    private final Activity activity;
    private boolean busy;
    private CancellationSignal cancellation;
    private final SharedPreferences prefs;
    private final Sender sender;

    interface Authentication {
        void failure(String str);

        void success(Cipher cipher);
    }

    interface Sender {
        void send(JSONObject jSONObject);
    }

    CredentialVault(Activity activity, Sender sender) {
        this.activity = activity;
        this.sender = sender;
        this.prefs = activity.getSharedPreferences("encrypted_court_login", 0);
    }

    private boolean biometricAvailable() {
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                BiometricManager biometricManager = (BiometricManager) this.activity.getSystemService(BiometricManager.class);
                return biometricManager != null && biometricManager.canAuthenticate(15) == 0;
            }
            if (Build.VERSION.SDK_INT >= 29) {
                BiometricManager biometricManager2 = (BiometricManager) this.activity.getSystemService(BiometricManager.class);
                return biometricManager2 != null && biometricManager2.canAuthenticate() == 0;
            }
            FingerprintManager fingerprintManager = (FingerprintManager) this.activity.getSystemService(FingerprintManager.class);
            return fingerprintManager != null && fingerprintManager.isHardwareDetected() && fingerprintManager.hasEnrolledFingerprints();
        } catch (Exception e) {
            return false;
        }
    }

    private JSONObject status() throws Exception {
        boolean z = this.prefs.contains("ciphertext") && this.prefs.contains("iv");
        return new JSONObject().put("available", true).put("biometricAvailable", biometricAvailable()).put("saved", z).put("biometricSaved", z && this.prefs.getBoolean("biometric", false));
    }

    void announce() {
        try {
            this.sender.send(new JSONObject().put("type", "credentialStatus").put("payload", status()));
        } catch (Exception e) {
        }
    }

    private void reply(String str, JSONObject jSONObject) {
        try {
            this.sender.send(new JSONObject().put("replyTo", str).put("success", true).put("payload", jSONObject));
        } catch (Exception e) {
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void reject(String str, String str2) {
        this.busy = false;
        try {
            this.sender.send(new JSONObject().put("replyTo", str).put("success", false).put("error", str2));
        } catch (Exception e) {
        }
    }

    void handle(JSONObject jSONObject) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, InvalidAlgorithmParameterException {
        String strOptString = jSONObject.optString("action");
        final String strOptString2 = jSONObject.optString("requestId");
        try {
            if ("credential-status".equals(strOptString)) {
                reply(strOptString2, status());
                return;
            }
            if (this.busy) {
                rejectWithoutReset(strOptString2, "أكمل عملية الحفظ أو البصمة الحالية أولًا.");
                return;
            }
            if ("credential-forget".equals(strOptString)) {
                clearSaved();
                reply(strOptString2, new JSONObject());
                announce();
                return;
            }
            if ("credential-save".equals(strOptString)) {
                save(jSONObject, strOptString2);
                return;
            }
            if ("credential-login".equals(strOptString) || "credential-biometric".equals(strOptString)) {
                if (!this.prefs.contains("ciphertext")) {
                    reject(strOptString2, "لا توجد بيانات دخول محفوظة على هذا الجهاز.");
                    return;
                }
                boolean z = this.prefs.getBoolean("biometric", false);
                if ("credential-biometric".equals(strOptString) && !z) {
                    reject(strOptString2, "احفظ بيانات الدخول مع تفعيل البصمة أولًا.");
                    return;
                }
                final byte[] bArrDecode = Base64.decode(this.prefs.getString("ciphertext", ""), 2);
                byte[] bArrDecode2 = Base64.decode(this.prefs.getString("iv", ""), 2);
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(2, key(z, false), new GCMParameterSpec(128, bArrDecode2));
                this.busy = true;
                if (!z) {
                    finishLogin(strOptString2, cipher, bArrDecode);
                } else {
                    authenticate(cipher, new Authentication() { // from class: ai.teable.albayda.court.preview.CredentialVault.1
                        @Override // ai.teable.albayda.court.preview.CredentialVault.Authentication
                        public void success(Cipher cipher2) {
                            CredentialVault.this.finishLogin(strOptString2, cipher2, bArrDecode);
                        }

                        @Override // ai.teable.albayda.court.preview.CredentialVault.Authentication
                        public void failure(String str) {
                            CredentialVault.this.reject(strOptString2, str);
                        }
                    });
                }
            }
        } catch (Exception e) {
            reject(strOptString2, "تعذر فتح البيانات المحفوظة. أدخل بياناتك يدويًا واحفظها من جديد إذا تغيّرت بصمات الجهاز.");
        }
    }

    private void rejectWithoutReset(String str, String str2) {
        try {
            this.sender.send(new JSONObject().put("replyTo", str).put("success", false).put("error", str2));
        } catch (Exception e) {
        }
    }

    private SecretKey key(boolean z, boolean z2) throws Exception {
        String str = z ? BIO_KEY : BASIC_KEY;
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        SecretKey secretKey = (SecretKey) keyStore.getKey(str, null);
        if (secretKey != null) {
            return secretKey;
        }
        if (z2) {
            KeyGenerator keyGenerator = KeyGenerator.getInstance("AES", "AndroidKeyStore");
            KeyGenParameterSpec.Builder userAuthenticationRequired = new KeyGenParameterSpec.Builder(str, 3).setBlockModes("GCM").setEncryptionPaddings("NoPadding").setRandomizedEncryptionRequired(true).setUserAuthenticationRequired(z);
            if (z) {
                if (Build.VERSION.SDK_INT >= 30) {
                    userAuthenticationRequired.setUserAuthenticationParameters(0, 2);
                } else {
                    userAuthenticationRequired.setUserAuthenticationValidityDurationSeconds(-1);
                }
                if (Build.VERSION.SDK_INT >= 24) {
                    userAuthenticationRequired.setInvalidatedByBiometricEnrollment(true);
                }
            }
            keyGenerator.init(userAuthenticationRequired.build());
            return keyGenerator.generateKey();
        }
        throw new Exception("Missing device key");
    }

    private Cipher encryptionCipher(boolean z) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        try {
            cipher.init(1, key(z, true));
        } catch (KeyPermanentlyInvalidatedException e) {
            KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
            keyStore.load(null);
            keyStore.deleteEntry(z ? BIO_KEY : BASIC_KEY);
            cipher.init(1, key(z, true));
        }
        return cipher;
    }

    private void save(JSONObject jSONObject, final String str) throws Exception {
        String strTrim = jSONObject.optString("name").trim();
        String strNormalizeDigits = normalizeDigits(jSONObject.optString("password"));
        if (strTrim.length() >= 3 && strTrim.length() <= 60 && strNormalizeDigits.matches("[0-9]{6,128}")) {
            final byte[] bytes = new JSONObject().put("name", strTrim).put("password", strNormalizeDigits).toString().getBytes("UTF-8");
            this.busy = true;
            AlertDialog.Builder onCancelListener = new AlertDialog.Builder(this.activity).setTitle("حفظ بيانات الدخول").setMessage("ستُحفظ بيانات هذا الحساب مشفّرة على هذا الهاتف فقط.").setNegativeButton("إلغاء", new DialogInterface.OnClickListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda3
                @Override // android.content.DialogInterface.OnClickListener
                public final void onClick(DialogInterface dialogInterface, int i) {
                    CredentialVault.this.m2lambda$save$0$aiteablealbaydacourtpreviewCredentialVault(bytes, str, dialogInterface, i);
                }
            }).setOnCancelListener(new DialogInterface.OnCancelListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda4
                @Override // android.content.DialogInterface.OnCancelListener
                public final void onCancel(DialogInterface dialogInterface) {
                    CredentialVault.this.m3lambda$save$1$aiteablealbaydacourtpreviewCredentialVault(bytes, str, dialogInterface);
                }
            });
            if (biometricAvailable()) {
                onCancelListener.setPositiveButton("حفظ وتفعيل البصمة", new DialogInterface.OnClickListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda5
                    @Override // android.content.DialogInterface.OnClickListener
                    public final void onClick(DialogInterface dialogInterface, int i) {
                        CredentialVault.this.m4lambda$save$2$aiteablealbaydacourtpreviewCredentialVault(str, bytes, dialogInterface, i);
                    }
                });
                onCancelListener.setNeutralButton("حفظ فقط", new DialogInterface.OnClickListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda6
                    @Override // android.content.DialogInterface.OnClickListener
                    public final void onClick(DialogInterface dialogInterface, int i) {
                        CredentialVault.this.m5lambda$save$3$aiteablealbaydacourtpreviewCredentialVault(str, bytes, dialogInterface, i);
                    }
                });
            } else {
                onCancelListener.setPositiveButton("حفظ على هذا الجهاز", new DialogInterface.OnClickListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda7
                    @Override // android.content.DialogInterface.OnClickListener
                    public final void onClick(DialogInterface dialogInterface, int i) {
                        CredentialVault.this.m6lambda$save$4$aiteablealbaydacourtpreviewCredentialVault(str, bytes, dialogInterface, i);
                    }
                });
            }
            this.activeDialog = onCancelListener.show();
            return;
        }
        reject(str, "كلمة المرور أرقام فقط، من 6 إلى 128 رقمًا.");
    }

    /* renamed from: lambda$save$0$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m2lambda$save$0$aiteablealbaydacourtpreviewCredentialVault(byte[] bArr, String str, DialogInterface dialogInterface, int i) {
        Arrays.fill(bArr, (byte) 0);
        reject(str, "تم إلغاء حفظ بيانات الدخول.");
    }

    /* renamed from: lambda$save$1$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m3lambda$save$1$aiteablealbaydacourtpreviewCredentialVault(byte[] bArr, String str, DialogInterface dialogInterface) {
        Arrays.fill(bArr, (byte) 0);
        reject(str, "تم إلغاء حفظ بيانات الدخول.");
    }

    /* renamed from: lambda$save$2$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m4lambda$save$2$aiteablealbaydacourtpreviewCredentialVault(String str, byte[] bArr, DialogInterface dialogInterface, int i) {
        encrypt(str, bArr, true);
    }

    /* renamed from: lambda$save$3$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m5lambda$save$3$aiteablealbaydacourtpreviewCredentialVault(String str, byte[] bArr, DialogInterface dialogInterface, int i) {
        encrypt(str, bArr, false);
    }

    /* renamed from: lambda$save$4$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m6lambda$save$4$aiteablealbaydacourtpreviewCredentialVault(String str, byte[] bArr, DialogInterface dialogInterface, int i) {
        encrypt(str, bArr, false);
    }

    private String normalizeDigits(String str) {
        StringBuilder sb = new StringBuilder();
        for (char c : str.toCharArray()) {
            if (c >= 1632 && c <= 1641) {
                sb.append((char) ((c + '0') - 1632));
            } else if (c >= 1776 && c <= 1785) {
                sb.append((char) ((c + '0') - 1776));
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private void encrypt(final String str, final byte[] bArr, boolean z) {
        try {
            Cipher cipherEncryptionCipher = encryptionCipher(z);
            if (z) {
                authenticate(cipherEncryptionCipher, new Authentication() { // from class: ai.teable.albayda.court.preview.CredentialVault.2
                    @Override // ai.teable.albayda.court.preview.CredentialVault.Authentication
                    public void success(Cipher cipher) {
                        CredentialVault.this.persist(str, cipher, bArr, true);
                    }

                    @Override // ai.teable.albayda.court.preview.CredentialVault.Authentication
                    public void failure(String str2) {
                        Arrays.fill(bArr, (byte) 0);
                        CredentialVault.this.reject(str, str2);
                    }
                });
            } else {
                persist(str, cipherEncryptionCipher, bArr, false);
            }
        } catch (Exception e) {
            Arrays.fill(bArr, (byte) 0);
            reject(str, "تعذر حفظ بيانات الدخول على هذا الجهاز.");
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void persist(String requestId, Cipher cipher, byte[] bytes, boolean biometric) {
        try {
            if (!prefs.edit().putString("ciphertext", Base64.encodeToString(cipher.doFinal(bytes), 2)).putString("iv", Base64.encodeToString(cipher.getIV(), 2)).putBoolean("biometric", biometric).commit()) throw new Exception();
            busy = false;
            reply(requestId, new JSONObject());
            announce();
        } catch (Exception error) {
            reject(requestId, "تعذر حفظ البيانات. يمكنك الاستمرار بالدخول اليدوي.");
        } finally {
            Arrays.fill(bytes, (byte) 0);
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void finishLogin(String str, Cipher cipher, byte[] bArr) {
        byte[] bArrDoFinal = null;
        try {
            try {
                bArrDoFinal = cipher.doFinal(bArr);
                JSONObject jSONObject = new JSONObject(new String(bArrDoFinal, "UTF-8"));
                this.busy = false;
                reply(str, jSONObject);
                if (bArrDoFinal != null) {
                    Arrays.fill(bArrDoFinal, (byte) 0);
                }
            } catch (Exception e) {
                reject(str, "تعذر استخدام البيانات المحفوظة. سجّل الدخول يدويًا ثم احفظها مجددًا.");
                if (bArrDoFinal != null) {
                    Arrays.fill(bArrDoFinal, (byte) 0);
                }
            }
        } catch (Throwable th) {
            if (bArrDoFinal != null) {
                Arrays.fill(bArrDoFinal, (byte) 0);
            }
            throw th;
        }
    }

    private void authenticate(Cipher cipher, final Authentication authentication) {
        if (!biometricAvailable()) {
            authentication.failure("البصمة غير متاحة. سجّل بصمة في إعدادات الهاتف أو استخدم الدخول اليدوي.");
            return;
        }
        this.cancellation = new CancellationSignal();
        final boolean[] zArr = {false};
        final Authentication authentication2 = new Authentication() { // from class: ai.teable.albayda.court.preview.CredentialVault.3
            @Override // ai.teable.albayda.court.preview.CredentialVault.Authentication
            public void success(Cipher cipher2) {
                if (zArr[0]) {
                    return;
                }
                zArr[0] = true;
                CredentialVault.this.cancellation = null;
                if (CredentialVault.this.activeDialog != null) {
                    CredentialVault.this.activeDialog.dismiss();
                    CredentialVault.this.activeDialog = null;
                }
                if (cipher2 == null) {
                    authentication.failure("لم يتم تأكيد البصمة.");
                } else {
                    authentication.success(cipher2);
                }
            }

            @Override // ai.teable.albayda.court.preview.CredentialVault.Authentication
            public void failure(String str) {
                if (zArr[0]) {
                    return;
                }
                zArr[0] = true;
                CredentialVault.this.cancellation = null;
                if (CredentialVault.this.activeDialog != null) {
                    CredentialVault.this.activeDialog.dismiss();
                    CredentialVault.this.activeDialog = null;
                }
                authentication.failure(str);
            }
        };
        if (Build.VERSION.SDK_INT >= 28) {
            BiometricPrompt.Builder negativeButton = new BiometricPrompt.Builder(this.activity).setTitle("ALBAYDA COURT").setSubtitle("تأكيد البصمة لاستخدام بيانات الدخول المحفوظة").setNegativeButton("إلغاء", this.activity.getMainExecutor(), new DialogInterface.OnClickListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda0
                @Override // android.content.DialogInterface.OnClickListener
                public final void onClick(DialogInterface dialogInterface, int i) {
                    authentication2.failure("تم إلغاء التحقق بالبصمة.");
                }
            });
            if (Build.VERSION.SDK_INT >= 30) {
                negativeButton.setAllowedAuthenticators(15);
            }
            negativeButton.build().authenticate(new BiometricPrompt.CryptoObject(cipher), this.cancellation, this.activity.getMainExecutor(), new BiometricPrompt.AuthenticationCallback() { // from class: ai.teable.albayda.court.preview.CredentialVault.4
                @Override // android.hardware.biometrics.BiometricPrompt.AuthenticationCallback
                public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult authenticationResult) {
                    authentication2.success(authenticationResult.getCryptoObject() == null ? null : authenticationResult.getCryptoObject().getCipher());
                }

                @Override // android.hardware.biometrics.BiometricPrompt.AuthenticationCallback
                public void onAuthenticationError(int i, CharSequence charSequence) {
                    authentication2.failure(charSequence.toString());
                }
            });
            return;
        }
        this.activeDialog = new AlertDialog.Builder(this.activity).setTitle("تأكيد البصمة").setMessage("المس مستشعر البصمة في الهاتف.").setNegativeButton("إلغاء", new DialogInterface.OnClickListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda1
            @Override // android.content.DialogInterface.OnClickListener
            public final void onClick(DialogInterface dialogInterface, int i) {
                CredentialVault.this.m0x5300acf6(authentication2, dialogInterface, i);
            }
        }).setOnCancelListener(new DialogInterface.OnCancelListener() { // from class: ai.teable.albayda.court.preview.CredentialVault$$ExternalSyntheticLambda2
            @Override // android.content.DialogInterface.OnCancelListener
            public final void onCancel(DialogInterface dialogInterface) {
                CredentialVault.this.m1x528a46f7(authentication2, dialogInterface);
            }
        }).show();
        ((FingerprintManager) this.activity.getSystemService(FingerprintManager.class)).authenticate(new FingerprintManager.CryptoObject(cipher), this.cancellation, 0, new FingerprintManager.AuthenticationCallback() { // from class: ai.teable.albayda.court.preview.CredentialVault.5
            @Override // android.hardware.fingerprint.FingerprintManager.AuthenticationCallback
            public void onAuthenticationSucceeded(FingerprintManager.AuthenticationResult authenticationResult) {
                authentication2.success(authenticationResult.getCryptoObject() == null ? null : authenticationResult.getCryptoObject().getCipher());
            }

            @Override // android.hardware.fingerprint.FingerprintManager.AuthenticationCallback
            public void onAuthenticationError(int i, CharSequence charSequence) {
                authentication2.failure(charSequence.toString());
            }

            @Override // android.hardware.fingerprint.FingerprintManager.AuthenticationCallback
            public void onAuthenticationFailed() {
                if (CredentialVault.this.activeDialog != null) {
                    CredentialVault.this.activeDialog.setMessage("لم تتطابق البصمة. حاول مرة أخرى.");
                }
            }
        }, null);
    }

    /* renamed from: lambda$authenticate$6$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m0x5300acf6(Authentication authentication, DialogInterface dialogInterface, int i) {
        if (this.cancellation != null) {
            this.cancellation.cancel();
        }
        authentication.failure("تم إلغاء التحقق بالبصمة.");
    }

    /* renamed from: lambda$authenticate$7$ai-teable-albayda-court-preview-CredentialVault, reason: not valid java name */
    /* synthetic */ void m1x528a46f7(Authentication authentication, DialogInterface dialogInterface) {
        if (this.cancellation != null) {
            this.cancellation.cancel();
        }
        authentication.failure("تم إلغاء التحقق بالبصمة.");
    }

    void clearSaved() throws Exception {
        if (this.busy) {
            throw new Exception("An authentication operation is in progress");
        }
        if (!this.prefs.edit().clear().commit()) {
            throw new Exception("Could not clear saved credentials");
        }
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(BASIC_KEY)) {
            keyStore.deleteEntry(BASIC_KEY);
        }
        if (keyStore.containsAlias(BIO_KEY)) {
            keyStore.deleteEntry(BIO_KEY);
        }
    }

    void destroy() {
        if (this.cancellation != null) {
            this.cancellation.cancel();
        }
        if (this.activeDialog != null) {
            this.activeDialog.dismiss();
        }
    }
}
