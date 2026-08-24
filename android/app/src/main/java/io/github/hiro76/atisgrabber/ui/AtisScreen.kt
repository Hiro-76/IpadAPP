package io.github.hiro76.atisgrabber.ui

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.hiro76.atisgrabber.data.Recording
import io.github.hiro76.atisgrabber.schedule.Schedule

@Composable
fun AtisScreen(
    state: UiState,
    onSearch: (String) -> Unit,
    onSelectFeed: (String, String) -> Unit,
    onSetEnabled: (Boolean) -> Unit,
    onSetMinute: (Int) -> Unit,
    onSetSecond: (Int) -> Unit,
    onSetInterval: (Int) -> Unit,
    onSetCaptureSeconds: (Int) -> Unit,
    onSetRetentionDays: (Int) -> Unit,
    onSetWifiOnly: (Boolean) -> Unit,
    onSetUseAlarmClock: (Boolean) -> Unit,
    onSetNotify: (Boolean) -> Unit,
    onCaptureNow: () -> Unit,
    onPlay: (Recording) -> Unit,
    onStop: () -> Unit,
    onDelete: (Recording) -> Unit,
    onShare: (Recording) -> Unit,
    onRefresh: () -> Unit,
    onOpenUrl: (String) -> Unit,
    onRequestExactAlarm: () -> Unit,
    onRequestBatteryExemption: () -> Unit,
    onMessageShown: () -> Unit,
) {
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            onMessageShown()
        }
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { StatusCard(state, onSetEnabled, onCaptureNow) }
            item { FeedCard(state, onSearch, onSelectFeed, onOpenUrl) }
            item { ScheduleCard(state, onSetMinute, onSetSecond, onSetInterval, onSetCaptureSeconds, onSetRetentionDays, onSetWifiOnly, onSetUseAlarmClock, onSetNotify) }
            item { ReliabilityCard(state, onRequestExactAlarm, onRequestBatteryExemption) }
            item { RecordingsHeader(state, onRefresh) }
            items(state.recordings, key = { it.file.absolutePath }) { recording ->
                RecordingRow(
                    recording = recording,
                    playing = state.playing == recording.file.absolutePath,
                    onPlay = { onPlay(recording) },
                    onStop = onStop,
                    onShare = { onShare(recording) },
                    onDelete = { onDelete(recording) },
                )
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
private fun StatusCard(state: UiState, onSetEnabled: (Boolean) -> Unit, onCaptureNow: () -> Unit) {
    SectionCard("ATIS 自動取得") {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("毎時の自動取得", Modifier.weight(1f))
            Switch(checked = state.config.enabled, onCheckedChange = onSetEnabled)
        }
        val next = state.nextRunAt
        if (state.config.enabled && state.config.hasFeed && next != null) {
            Text("次回 ${formatLocalWithUtc(next)}", style = MaterialTheme.typography.bodyMedium)
            Text(
                formatCountdown(next - System.currentTimeMillis()),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
            )
        } else if (!state.config.hasFeed) {
            Text("下でフィードを選ぶと動き出す", style = MaterialTheme.typography.bodySmall)
        } else {
            Text("停止中", style = MaterialTheme.typography.bodySmall)
        }

        if (state.config.lastResultAt > 0L) {
            HorizontalDivider()
            Text(
                "前回 ${formatLocalShort(state.config.lastResultAt)}: ${state.config.lastResult}",
                style = MaterialTheme.typography.bodySmall,
                color = if (state.config.lastResultOk) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error,
            )
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onCaptureNow, enabled = !state.capturing && state.config.hasFeed) {
                Text(if (state.capturing) "取得中…" else "今すぐ取得")
            }
            if (state.capturing) {
                CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            }
        }
    }
}

@Composable
private fun FeedCard(
    state: UiState,
    onSearch: (String) -> Unit,
    onSelectFeed: (String, String) -> Unit,
    onOpenUrl: (String) -> Unit,
) {
    var icao by rememberSaveable(state.config.icao) { mutableStateOf(state.config.icao) }
    var manualMount by rememberSaveable { mutableStateOf("") }

    SectionCard("空港 / フィード") {
        if (state.config.hasFeed) {
            Text(state.config.label.ifBlank { state.config.mount }, fontWeight = FontWeight.Bold)
            Text(state.config.mount, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
        } else {
            Text("未選択", style = MaterialTheme.typography.bodySmall)
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = icao,
                onValueChange = { icao = it.uppercase() },
                label = { Text("ICAO（例 RJTT / KJFK）") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Button(onClick = { onSearch(icao) }, enabled = !state.searching) {
                Text(if (state.searching) "…" else "検索")
            }
        }

        if (state.searchResults.isNotEmpty()) {
            Text("ATIS が上に並ぶ。名前が空でも mount 名で判断できる。", style = MaterialTheme.typography.bodySmall)
            state.searchResults.forEach { feed ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            (if (feed.isAtis) "ATIS  " else "") + feed.label,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = if (feed.isAtis) FontWeight.Bold else FontWeight.Normal,
                        )
                        Text(feed.mount, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                    }
                    TextButton(onClick = { onSelectFeed(feed.mount, feed.label) }) { Text("選ぶ") }
                }
            }
        }

        if (state.config.recentFeeds.isNotEmpty()) {
            Text("最近使ったフィード", style = MaterialTheme.typography.bodySmall)
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                state.config.recentFeeds.forEach { feed ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "${feed.icao} ${feed.mount}",
                            Modifier.weight(1f),
                            fontFamily = FontFamily.Monospace,
                            style = MaterialTheme.typography.bodySmall,
                        )
                        TextButton(onClick = { onSelectFeed(feed.mount, feed.label) }) { Text("選ぶ") }
                    }
                }
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = manualMount,
                onValueChange = { manualMount = it.trim() },
                label = { Text("mount 名を直接入れる") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Button(
                onClick = {
                    onSelectFeed(manualMount, manualMount)
                    manualMount = ""
                },
                enabled = manualMount.isNotBlank(),
            ) { Text("使う") }
        }

        OutlinedButton(onClick = { onOpenUrl("https://www.liveatc.net/search/?icao=${icao.trim().uppercase()}") }) {
            Text("LiveATC のページを開く")
        }
    }
}

@Composable
private fun ScheduleCard(
    state: UiState,
    onSetMinute: (Int) -> Unit,
    onSetSecond: (Int) -> Unit,
    onSetInterval: (Int) -> Unit,
    onSetCaptureSeconds: (Int) -> Unit,
    onSetRetentionDays: (Int) -> Unit,
    onSetWifiOnly: (Boolean) -> Unit,
    onSetUseAlarmClock: (Boolean) -> Unit,
    onSetNotify: (Boolean) -> Unit,
) {
    val config = state.config
    SectionCard("取得タイミング") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Schedule.INTERVALS.forEach { interval ->
                FilterChip(
                    selected = config.intervalMinutes == interval,
                    onClick = { onSetInterval(interval) },
                    label = { Text("${interval}分毎") },
                )
            }
        }
        Stepper("何分過ぎ", "${config.minuteOfHour} 分", config.minuteOfHour, 0, config.intervalMinutes - 1, 1, onSetMinute)
        Stepper("さらに", "${config.secondOffset} 秒", config.secondOffset, 0, 55, 5, onSetSecond)
        Stepper("録音の長さ", "${config.captureSeconds} 秒", config.captureSeconds, 30, 300, 30, onSetCaptureSeconds)
        Stepper(
            "保存期間",
            if (config.retentionDays == 0) "消さない" else "${config.retentionDays} 日",
            config.retentionDays, 0, 30, 1, onSetRetentionDays,
        )
        Toggle("Wi-Fi のときだけ取得", config.wifiOnly, onSetWifiOnly)
        Toggle("アラーム扱いで確実に起こす", config.useAlarmClock, onSetUseAlarmClock)
        Toggle("取得結果を通知", config.notifyOnFinish, onSetNotify)
    }
}

@Composable
private fun ReliabilityCard(
    state: UiState,
    onRequestExactAlarm: () -> Unit,
    onRequestBatteryExemption: () -> Unit,
) {
    SectionCard("時間どおりに動かすために") {
        if (!state.canScheduleExact && !state.config.useAlarmClock) {
            Text(
                "「正確なアラーム」が許可されていないため、取得が数分ずれることがある。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
            OutlinedButton(onClick = onRequestExactAlarm) { Text("正確なアラームを許可する") }
        }
        Text(
            "端末の省電力機能に止められると取得が飛ぶ。電池の最適化から除外しておく。",
            style = MaterialTheme.typography.bodySmall,
        )
        OutlinedButton(onClick = onRequestBatteryExemption) { Text("電池の最適化を外す") }
    }
}

@Composable
private fun RecordingsHeader(state: UiState, onRefresh: () -> Unit) {
    val total = state.recordings.sumOf { it.sizeBytes }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("録音", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("${state.recordings.size} 件 / ${formatSize(total)}", style = MaterialTheme.typography.bodySmall)
        }
        TextButton(onClick = onRefresh) { Text("更新") }
    }
}

@Composable
private fun RecordingRow(
    recording: Recording,
    playing: Boolean,
    onPlay: () -> Unit,
    onStop: () -> Unit,
    onShare: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(formatUtcDay(recording.recordedAtUtc), fontWeight = FontWeight.Bold)
            Text(
                "${recording.mount} · ${formatSize(recording.sizeBytes)} · ${formatLocalShort(recording.recordedAtUtc.toInstant().toEpochMilli())} 現地",
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { if (playing) onStop() else onPlay() }) {
                    Text(if (playing) "停止" else "再生")
                }
                OutlinedButton(onClick = onShare) { Text("共有") }
                Spacer(Modifier.width(4.dp))
                TextButton(onClick = onDelete) { Text("削除") }
            }
        }
    }
}

@Composable
private fun Stepper(
    label: String,
    value: String,
    current: Int,
    min: Int,
    max: Int,
    step: Int,
    onChange: (Int) -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            Text(value, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
        }
        OutlinedButton(onClick = { onChange((current - step).coerceAtLeast(min)) }, enabled = current > min) { Text("−") }
        Spacer(Modifier.width(8.dp))
        OutlinedButton(onClick = { onChange((current + step).coerceAtMost(max)) }, enabled = current < max) { Text("＋") }
    }
}

@Composable
private fun Toggle(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

/** Kept out of the composables above so the activity can hand the intent to the system. */
fun shareChooser(intent: Intent): Intent = Intent.createChooser(intent, "ATIS を共有")
