package io.github.hiro76.atisgrabber.capture

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import io.github.hiro76.atisgrabber.data.ConfigStore
import io.github.hiro76.atisgrabber.data.RecordingStore
import io.github.hiro76.atisgrabber.net.LiveAtcClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import java.io.File
import java.time.Instant

sealed interface CaptureResult {
    data class Success(val file: File, val bytes: Long, val seconds: Int) : CaptureResult
    data class Failure(val reason: String) : CaptureResult
}

/**
 * Records the feed's audio for a fixed stretch of time. LiveATC serves MP3, and an ATIS broadcast
 * simply repeats, so the bytes are written to disk exactly as they arrive — no decoding, and any
 * two-minute slice contains at least one full loop of the message.
 */
object AtisCapture {

    private val running = Mutex()
    private const val MIN_USEFUL_BYTES = 8 * 1024

    val isRunning: Boolean get() = running.isLocked

    suspend fun run(
        context: Context,
        client: LiveAtcClient = LiveAtcClient(),
        onProgress: (elapsedSeconds: Int, totalSeconds: Int) -> Unit = { _, _ -> },
    ): CaptureResult {
        if (!running.tryLock()) return CaptureResult.Failure("すでに取得中です")
        try {
            val result = capture(context, client, onProgress)
            record(context, result)
            return result
        } finally {
            running.unlock()
        }
    }

    private suspend fun capture(
        context: Context,
        client: LiveAtcClient,
        onProgress: (Int, Int) -> Unit,
    ): CaptureResult {
        val config = ConfigStore.current(context)
        if (!config.hasFeed) return CaptureResult.Failure("フィードが選ばれていません")
        if (config.wifiOnly && !onUnmeteredNetwork(context)) {
            return CaptureResult.Failure("Wi-Fi でないため見送りました")
        }

        val seconds = config.captureSeconds.coerceIn(10, 600)
        val target = RecordingStore.fileFor(context, config.mount, Instant.now())
        val partial = File(target.parentFile, target.name + ".part")

        return try {
            val url = client.resolveStreamUrl(config.mount)
            val bytes = download(client, url, partial, seconds, onProgress)
            when {
                bytes < MIN_USEFUL_BYTES -> {
                    partial.delete()
                    CaptureResult.Failure("音声が届きませんでした（フィード停止中かも）")
                }
                else -> {
                    target.delete()
                    if (!partial.renameTo(target)) {
                        partial.delete()
                        CaptureResult.Failure("ファイルを保存できませんでした")
                    } else {
                        RecordingStore.prune(context, config.retentionDays)
                        CaptureResult.Success(target, bytes, seconds)
                    }
                }
            }
        } catch (cancellation: CancellationException) {
            partial.delete()
            throw cancellation
        } catch (error: Throwable) {
            partial.delete()
            CaptureResult.Failure(error.message ?: error.javaClass.simpleName)
        }
    }

    private suspend fun download(
        client: LiveAtcClient,
        url: String,
        destination: File,
        seconds: Int,
        onProgress: (Int, Int) -> Unit,
    ): Long = withContext(Dispatchers.IO) {
        client.openStream(url).use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}")
            val type = response.header("Content-Type").orEmpty()
            if (type.startsWith("text/") || type.contains("html")) {
                error("音声ではなくページが返りました（mount 名を確認）")
            }
            val body = response.body ?: error("空のレスポンス")
            val deadline = System.nanoTime() + seconds * 1_000_000_000L
            var written = 0L
            var reported = -1
            val buffer = ByteArray(16 * 1024)
            body.byteStream().use { input ->
                destination.parentFile?.mkdirs()
                destination.outputStream().use { output ->
                    while (System.nanoTime() < deadline) {
                        currentCoroutineContext().ensureActive()
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                        written += read
                        val elapsed = seconds - ((deadline - System.nanoTime()) / 1_000_000_000L).toInt()
                        if (elapsed != reported) {
                            reported = elapsed
                            onProgress(elapsed.coerceIn(0, seconds), seconds)
                        }
                    }
                    output.flush()
                }
            }
            written
        }
    }

    private fun record(context: Context, result: CaptureResult) {
        val summary = when (result) {
            is CaptureResult.Success -> "${result.file.name}（${result.bytes / 1024} KB）"
            is CaptureResult.Failure -> result.reason
        }
        val ok = result is CaptureResult.Success
        ConfigStore.update(context) { config ->
            config.copy(lastResult = summary, lastResultAt = System.currentTimeMillis(), lastResultOk = ok)
        }
        if (ConfigStore.current(context).notifyOnFinish) {
            Notifications.result(context, ok, summary)
        }
    }

    private fun onUnmeteredNetwork(context: Context): Boolean {
        val manager = context.getSystemService(ConnectivityManager::class.java) ?: return true
        val capabilities = manager.getNetworkCapabilities(manager.activeNetwork) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED)
    }
}
