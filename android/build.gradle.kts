// Kinbox-App für Android: eine WebView, die Popup + Einstellungen der Erweiterung anzeigt.
// Bauen: ./gradlew assembleRelease  (Signatur über KINBOX_KEYSTORE / KINBOX_KEYSTORE_PASSWORD, sonst Debug-Schlüssel)
plugins { id("com.android.application") version "9.4.1" }

// Version = APP_VERSION aus server/server.py (eine Stelle für alles); 3.7.0 → versionCode 30700
val kinboxVersion = Regex("APP_VERSION = \"([0-9.]+)\"").find(file("../server/server.py").readText())!!.groupValues[1]

android {
    namespace = "io.github.b4turnatur.kinbox"
    compileSdk = 36
    defaultConfig {
        applicationId = "io.github.b4turnatur.kinbox"
        minSdk = 29
        targetSdk = 36
        versionCode = kinboxVersion.split(".").map(String::toInt).let { (a, b, c) -> a * 10000 + b * 100 + c }
        versionName = kinboxVersion
    }
    // Die Oberfläche kommt 1:1 aus der Erweiterung – keine Kopie im Repo
    sourceSets["main"].assets.srcDir("../extension")
    signingConfigs {
        create("release") {
            val ks = System.getenv("KINBOX_KEYSTORE")
            if (ks != null) {
                storeFile = file(ks)
                storePassword = System.getenv("KINBOX_KEYSTORE_PASSWORD")
                keyAlias = "kinbox"
                keyPassword = System.getenv("KINBOX_KEYSTORE_PASSWORD")
            } else initWith(getByName("debug"))
        }
    }
    buildTypes { release { signingConfig = signingConfigs["release"] } }
}
