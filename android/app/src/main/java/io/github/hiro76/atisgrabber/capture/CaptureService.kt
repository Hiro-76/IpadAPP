package io.github.hiro76.atisgrabber.capture

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import io.github.hiro76.atisgrabber.data.ConfigStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Runs one capture in the foreground so the download survives a screen-off device. Started from the
 * hourly alarm, or from the "今すぐ取得" button.
 */
class CaptureService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val config = ConfigStore.current(this)
        val title = "ATIS 取得中"
        val subject = config.label.ifBlank { config.mount }.ifBlank { "フィード未設定" }
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        } else {
            0
        }
        ServiceCompat.startForeground(
            this,
            Notifications.ID_CAPTURE,
            Notifications.capturing(this, title, subject),
            type,
        )
        acquireWakeLock(config.captureSeconds)

        scope.launch {
            AtisCapture.run(this@CaptureService) { elapsed, total ->
                val notification = Notifications.capturing(
                    this@CaptureService,
                    title,
                    "$subject  $elapsed / $total 秒",
                )
                runCatching {
                    NotificationManagerCompat.from(this@CaptureService)
                        .notify(Notifications.ID_CAPTURE, notification)
                }
            }
            stopSelf(startId)
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        scope.cancel()
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
        super.onDestroy()
    }

    private fun acquireWakeLock(captureSeconds: Int) {
        val power = getSystemService(PowerManager::class.java) ?: return
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AtisGrabber:capture").apply {
            setReferenceCounted(false)
            acquire((captureSeconds + 60) * 1000L)
        }
    }

    companion object {
        fun intent(context: Context): Intent = Intent(context, CaptureService::class.java)
    }
}
