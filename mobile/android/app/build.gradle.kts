plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Store releases require upload signing; development APKs use the debug build type.
val signedRelease = System.getenv("WEEDZ_SIGNED_RELEASE") == "true"
val releaseRequested = gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) }
require(!releaseRequested || signedRelease) { "Release builds require the mobile-release workflow signing configuration" }
fun signingSetting(name: String): String = System.getenv(name)?.takeIf { it.isNotEmpty() }
    ?: error("Missing release signing setting: $name")

android {
    namespace = "org.example.weedz"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = if (signedRelease) signingSetting("ANDROID_APPLICATION_ID") else "org.example.weedz"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (signedRelease) {
            create("upload") {
                storeFile = file(signingSetting("WEEDZ_ANDROID_KEYSTORE_PATH"))
                require(storeFile!!.isFile) { "Release keystore file is missing" }
                storePassword = signingSetting("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = signingSetting("ANDROID_KEY_ALIAS")
                keyPassword = signingSetting("ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            if (signedRelease) signingConfig = signingConfigs.getByName("upload")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
