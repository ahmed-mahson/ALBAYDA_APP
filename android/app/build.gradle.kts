plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val appUrl = providers.gradleProperty("appUrl").orNull?.trim().orEmpty()
val parsedAppUrl = runCatching { java.net.URI(appUrl) }.getOrNull()
require(
    parsedAppUrl?.scheme == "https" &&
        !parsedAppUrl.host.isNullOrBlank() &&
        parsedAppUrl.userInfo == null &&
        parsedAppUrl.query == null &&
        parsedAppUrl.fragment == null,
) {
    "Pass the deployed HTTPS application URL with -PappUrl=https://your-host/"
}
val normalizedAppUrl = if (appUrl.endsWith("/")) appUrl else "$appUrl/"
val escapedAppUrl = normalizedAppUrl.replace("\\", "\\\\").replace("\"", "\\\"")

android {
    namespace = "ye.court.albayda"
    compileSdk = 35

    defaultConfig {
        applicationId = "ye.court.albayda"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        buildConfigField("String", "APP_BASE_URL", "\"$escapedAppUrl\"")
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}
