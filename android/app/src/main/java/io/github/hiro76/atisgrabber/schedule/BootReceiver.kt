package io.github.hiro76.atisgrabber.schedule

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Alarms do not survive a reboot, a reinstall, or a clock change; this puts them back. */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        AtisScheduler.reschedule(context.applicationContext)
    }
}
