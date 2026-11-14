package org.example.weedz

import android.content.Context
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger
        MethodChannel(
            messenger,
            "weedz/device-storage",
            io.flutter.plugin.common.StandardMethodCodec.INSTANCE,
            messenger.makeBackgroundTaskQueue()
        ).setMethodCallHandler { call, result ->
            if (call.method != "flush") {
                result.notImplemented()
            } else {
                // flutter_secure_storage 11 uses apply(). A synchronous commit waits
                // for earlier writes before Dart may send DELETE or clear its token.
                // Names match the explicitly configured plugin storageNamespace.
                val names = listOf(
                    "weedz.device",
                    "FlutterSecureKeyStorage:weedz.device",
                    "FlutterSecureStorageConfiguration:weedz.device"
                )
                try {
                    val saved = names.all { name ->
                        getSharedPreferences(name, Context.MODE_PRIVATE).edit().commit()
                    }
                    if (saved) result.success(null)
                    else result.error("storage", "Secure write could not be committed", null)
                } catch (_: Exception) {
                    result.error("storage", "Secure write could not be committed", null)
                }
            }
        }
    }
}
