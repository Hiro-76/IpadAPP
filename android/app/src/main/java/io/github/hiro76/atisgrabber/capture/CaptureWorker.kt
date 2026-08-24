package io.github.hiro76.atisgrabber.capture

import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import io.github.hiro76.atisgrabber.data.ConfigStore

/**
 * Fallback path. Android occasionally refuses a foreground service started from the background; when
 * that happens the alarm hands the same capture to WorkManager instead, which is allowed to run it.
 */
class CaptureWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val result = AtisCapture.run(applicationContext)
        return if (result is CaptureResult.Success) Result.success() else Result.failure()
    }

    override suspend fun getForegroundInfo(): ForegroundInfo {
        val config = ConfigStore.current(applicationContext)
        val subject = config.label.ifBlank { config.mount }
        val notification = Notifications.capturing(applicationContext, "ATIS 取得中", subject)
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(Notifications.ID_CAPTURE, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(Notifications.ID_CAPTURE, notification)
        }
    }

    companion object {
        private const val NAME = "atis-capture"

        fun enqueue(context: Context) {
            val request = OneTimeWorkRequestBuilder<CaptureWorker>()
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(NAME, ExistingWorkPolicy.KEEP, request)
        }
    }
}
