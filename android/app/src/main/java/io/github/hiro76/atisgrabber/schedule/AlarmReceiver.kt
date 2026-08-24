package io.github.hiro76.atisgrabber.schedule

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import io.github.hiro76.atisgrabber.capture.CaptureService
import io.github.hiro76.atisgrabber.capture.CaptureWorker

class AlarmReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        val app = context.applicationContext
        try {
            ContextCompat.startForegroundService(app, CaptureService.intent(app))
        } catch (error: Throwable) {
            // Android can refuse a background foreground-service start; WorkManager still may run it.
            Log.w("AtisGrabber", "foreground service refused, falling back to WorkManager", error)
            CaptureWorker.enqueue(app)
        }
        // Skip the slot that just fired, even if the alarm arrived a hair early.
        AtisScheduler.reschedule(app, System.currentTimeMillis() + 5_000L)
    }

    companion object {
        const val ACTION_CAPTURE = "io.github.hiro76.atisgrabber.CAPTURE"
    }
}
