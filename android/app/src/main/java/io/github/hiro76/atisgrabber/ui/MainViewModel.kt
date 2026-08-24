package io.github.hiro76.atisgrabber.ui

import android.app.Application
import android.content.Intent
import android.media.MediaPlayer
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.hiro76.atisgrabber.capture.AtisCapture
import io.github.hiro76.atisgrabber.capture.CaptureService
import io.github.hiro76.atisgrabber.data.Config
import io.github.hiro76.atisgrabber.data.ConfigStore
import io.github.hiro76.atisgrabber.data.Recording
import io.github.hiro76.atisgrabber.data.RecordingStore
import io.github.hiro76.atisgrabber.net.Feed
import io.github.hiro76.atisgrabber.net.LiveAtcClient
import io.github.hiro76.atisgrabber.schedule.AtisScheduler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class UiState(
    val config: Config = Config(),
    val recordings: List<Recording> = emptyList(),
    val searchResults: List<Feed> = emptyList(),
    val searching: Boolean = false,
    val message: String? = null,
    val nextRunAt: Long? = null,
    val capturing: Boolean = false,
    val playing: String? = null,
    val canScheduleExact: Boolean = true,
)

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val client = LiveAtcClient()
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()
    private var player: MediaPlayer? = null

    init {
        ConfigStore.init(app)
        viewModelScope.launch {
            ConfigStore.state.collect { config -> _state.value = _state.value.copy(config = config) }
        }
        viewModelScope.launch {
            while (true) {
                _state.value = _state.value.copy(
                    nextRunAt = AtisScheduler.nextRunAt(app),
                    capturing = AtisCapture.isRunning,
                    canScheduleExact = AtisScheduler.canScheduleExact(app),
                )
                delay(1000)
            }
        }
        refreshRecordings()
    }

    fun refreshRecordings() {
        viewModelScope.launch {
            val list = withContext(Dispatchers.IO) { RecordingStore.list(getApplication()) }
            _state.value = _state.value.copy(recordings = list)
        }
    }

    fun dismissMessage() {
        _state.value = _state.value.copy(message = null)
    }

    fun search(icao: String) {
        val code = icao.trim().uppercase()
        if (code.isEmpty()) {
            _state.value = _state.value.copy(message = "ICAO コード（例: RJTT）を入れてください")
            return
        }
        updateConfig { it.copy(icao = code) }
        _state.value = _state.value.copy(searching = true, searchResults = emptyList(), message = null)
        viewModelScope.launch {
            val result = runCatching { client.searchFeeds(code) }
            _state.value = result.fold(
                onSuccess = { feeds ->
                    _state.value.copy(
                        searching = false,
                        searchResults = feeds,
                        message = if (feeds.isEmpty()) "$code のフィードが見つかりませんでした" else null,
                    )
                },
                onFailure = { error ->
                    _state.value.copy(
                        searching = false,
                        message = "検索に失敗しました: ${error.message ?: "不明なエラー"}",
                    )
                },
            )
        }
    }

    fun selectFeed(mount: String, label: String) {
        val trimmed = mount.trim()
        if (trimmed.isEmpty()) return
        updateConfig { config ->
            val recent = (listOf(
                io.github.hiro76.atisgrabber.data.RecentFeed(trimmed, label, config.icao),
            ) + config.recentFeeds).distinctBy { it.mount.lowercase() }.take(8)
            config.copy(mount = trimmed, label = label, recentFeeds = recent)
        }
        _state.value = _state.value.copy(searchResults = emptyList(), message = "$trimmed を使います")
    }

    fun setEnabled(enabled: Boolean) = updateConfig { it.copy(enabled = enabled) }

    fun setMinute(minute: Int) = updateConfig { it.copy(minuteOfHour = minute) }

    fun setSecondOffset(second: Int) = updateConfig { it.copy(secondOffset = second) }

    fun setInterval(minutes: Int) = updateConfig { config ->
        config.copy(intervalMinutes = minutes, minuteOfHour = config.minuteOfHour.coerceAtMost(minutes - 1))
    }

    fun setCaptureSeconds(seconds: Int) = updateConfig { it.copy(captureSeconds = seconds) }

    fun setRetentionDays(days: Int) = updateConfig { it.copy(retentionDays = days) }

    fun setWifiOnly(value: Boolean) = updateConfig { it.copy(wifiOnly = value) }

    fun setUseAlarmClock(value: Boolean) = updateConfig { it.copy(useAlarmClock = value) }

    fun setNotifyOnFinish(value: Boolean) = updateConfig { it.copy(notifyOnFinish = value) }

    fun captureNow() {
        val app = getApplication<Application>()
        if (!ConfigStore.current(app).hasFeed) {
            _state.value = _state.value.copy(message = "先にフィードを選んでください")
            return
        }
        runCatching { ContextCompat.startForegroundService(app, CaptureService.intent(app)) }
            .onFailure { _state.value = _state.value.copy(message = "取得を開始できませんでした: ${it.message}") }
        viewModelScope.launch {
            delay(1500)
            while (AtisCapture.isRunning) delay(1000)
            refreshRecordings()
        }
    }

    fun play(recording: Recording) {
        stopPlayback()
        runCatching {
            player = MediaPlayer().apply {
                setDataSource(recording.file.absolutePath)
                setOnCompletionListener { stopPlayback() }
                prepare()
                start()
            }
            _state.value = _state.value.copy(playing = recording.file.absolutePath)
        }.onFailure {
            _state.value = _state.value.copy(message = "再生できませんでした: ${it.message}")
        }
    }

    fun stopPlayback() {
        player?.runCatching {
            if (isPlaying) stop()
            release()
        }
        player = null
        _state.value = _state.value.copy(playing = null)
    }

    fun delete(recording: Recording) {
        if (_state.value.playing == recording.file.absolutePath) stopPlayback()
        RecordingStore.delete(recording)
        refreshRecordings()
    }

    fun shareIntent(recording: Recording): Intent {
        val uri = RecordingStore.shareUri(getApplication(), recording.file)
        return Intent(Intent.ACTION_SEND).apply {
            type = "audio/mpeg"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    override fun onCleared() {
        stopPlayback()
        super.onCleared()
    }

    private fun updateConfig(block: (Config) -> Config) {
        val app = getApplication<Application>()
        ConfigStore.update(app, block)
        AtisScheduler.reschedule(app)
        _state.value = _state.value.copy(nextRunAt = AtisScheduler.nextRunAt(app))
    }
}
