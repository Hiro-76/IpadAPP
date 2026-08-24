package io.github.hiro76.atisgrabber

import android.app.Application
import io.github.hiro76.atisgrabber.capture.Notifications
import io.github.hiro76.atisgrabber.data.ConfigStore
import io.github.hiro76.atisgrabber.schedule.AtisScheduler

class AtisApp : Application() {

    override fun onCreate() {
        super.onCreate()
        ConfigStore.init(this)
        Notifications.createChannels(this)
        AtisScheduler.reschedule(this)
    }
}
