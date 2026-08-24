package io.github.hiro76.atisgrabber.schedule

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import io.github.hiro76.atisgrabber.data.ConfigStore
import io.github.hiro76.atisgrabber.ui.MainActivity

/** Arms the alarm for the next capture, one at a time, re-arming after each firing. */
object AtisScheduler {

    private const val REQUEST_ALARM = 100
    private const val REQUEST_SHOW = 101

    /**
     * [notBefore] guards against re-arming the slot that has just fired: an alarm may arrive a few
     * milliseconds early, and without the slack the next trigger would land on the same slot again.
     */
    fun reschedule(context: Context, notBefore: Long = System.currentTimeMillis()): Long? {
        val app = context.applicationContext
        val alarms = app.getSystemService(AlarmManager::class.java) ?: return null
        val trigger = alarmPendingIntent(app)
        alarms.cancel(trigger)

        val config = ConfigStore.current(app)
        if (!config.enabled || !config.hasFeed) return null

        val at = nextRunAt(app, notBefore) ?: return null
        when {
            // An alarm-clock alarm is the one kind Doze never delays, and it needs no extra
            // permission on Android 12+. The cost is the alarm icon in the status bar.
            config.useAlarmClock ->
                alarms.setAlarmClock(AlarmManager.AlarmClockInfo(at, showPendingIntent(app)), trigger)

            canScheduleExact(app) ->
                alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, trigger)

            else ->
                alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, trigger)
        }
        return at
    }

    fun cancel(context: Context) {
        val app = context.applicationContext
        app.getSystemService(AlarmManager::class.java)?.cancel(alarmPendingIntent(app))
    }

    /** When the next capture is due, whether or not an alarm is currently armed. */
    fun nextRunAt(context: Context, notBefore: Long = System.currentTimeMillis()): Long? {
        val config = ConfigStore.current(context)
        return Schedule.nextTrigger(
            nowMillis = notBefore,
            minuteOfHour = config.minuteOfHour,
            secondOffset = config.secondOffset,
            intervalMinutes = config.intervalMinutes,
        )
    }

    fun canScheduleExact(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        val alarms = context.getSystemService(AlarmManager::class.java) ?: return false
        return alarms.canScheduleExactAlarms()
    }

    private fun alarmPendingIntent(context: Context): PendingIntent =
        PendingIntent.getBroadcast(
            context,
            REQUEST_ALARM,
            Intent(context, AlarmReceiver::class.java).setAction(AlarmReceiver.ACTION_CAPTURE),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

    private fun showPendingIntent(context: Context): PendingIntent =
        PendingIntent.getActivity(
            context,
            REQUEST_SHOW,
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
}
