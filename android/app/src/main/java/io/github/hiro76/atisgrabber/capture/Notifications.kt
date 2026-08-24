package io.github.hiro76.atisgrabber.capture

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import io.github.hiro76.atisgrabber.R
import io.github.hiro76.atisgrabber.ui.MainActivity

object Notifications {

    const val CHANNEL_CAPTURE = "capture"
    const val CHANNEL_RESULT = "result"
    const val ID_CAPTURE = 1001
    const val ID_RESULT = 1002

    fun createChannels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_CAPTURE, "取得中", NotificationManager.IMPORTANCE_LOW).apply {
                description = "ATIS を取得している間だけ出る通知"
                setShowBadge(false)
            },
        )
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_RESULT, "取得結果", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "取得できた / 失敗した の通知"
            },
        )
    }

    fun capturing(context: Context, title: String, text: String): Notification =
        NotificationCompat.Builder(context, CHANNEL_CAPTURE)
            .setSmallIcon(R.drawable.ic_stat_atis)
            .setContentTitle(title)
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openApp(context))
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()

    fun result(context: Context, ok: Boolean, text: String) {
        val notification = NotificationCompat.Builder(context, CHANNEL_RESULT)
            .setSmallIcon(R.drawable.ic_stat_atis)
            .setContentTitle(if (ok) "ATIS を取得しました" else "ATIS を取得できませんでした")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setContentIntent(openApp(context))
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(ID_RESULT, notification) }
    }

    private fun openApp(context: Context): PendingIntent {
        val intent = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        return PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}
