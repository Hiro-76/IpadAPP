package io.github.hiro76.atisgrabber.ui

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.hiro76.atisgrabber.schedule.AtisScheduler

class MainActivity : ComponentActivity() {

    private val requestNotifications =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        askForNotificationPermission()

        setContent {
            AtisTheme {
                val model: MainViewModel = viewModel()
                val state by model.state.collectAsState()
                AtisScreen(
                    state = state,
                    onSearch = model::search,
                    onSelectFeed = model::selectFeed,
                    onSetEnabled = model::setEnabled,
                    onSetMinute = model::setMinute,
                    onSetSecond = model::setSecondOffset,
                    onSetInterval = model::setInterval,
                    onSetCaptureSeconds = model::setCaptureSeconds,
                    onSetRetentionDays = model::setRetentionDays,
                    onSetWifiOnly = model::setWifiOnly,
                    onSetUseAlarmClock = model::setUseAlarmClock,
                    onSetNotify = model::setNotifyOnFinish,
                    onCaptureNow = model::captureNow,
                    onPlay = model::play,
                    onStop = model::stopPlayback,
                    onDelete = model::delete,
                    onShare = { recording -> startActivity(shareChooser(model.shareIntent(recording))) },
                    onRefresh = model::refreshRecordings,
                    onOpenUrl = ::openUrl,
                    onRequestExactAlarm = ::openExactAlarmSettings,
                    onRequestBatteryExemption = ::requestBatteryExemption,
                    onMessageShown = model::dismissMessage,
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // Settings may have changed outside the app (exact alarms, battery); re-arm to be safe.
        AtisScheduler.reschedule(this)
    }

    private fun askForNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun openUrl(url: String) {
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
    }

    private fun openExactAlarmSettings() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            runCatching {
                startActivity(
                    Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:$packageName")),
                )
            }
        }
    }

    private fun requestBatteryExemption() {
        runCatching {
            startActivity(
                Intent(
                    Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                    Uri.parse("package:$packageName"),
                ),
            )
        }.onFailure {
            runCatching { startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        }
    }
}
