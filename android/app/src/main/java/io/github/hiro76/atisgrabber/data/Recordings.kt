package io.github.hiro76.atisgrabber.data

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File
import java.time.Instant
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/** One captured ATIS file. */
data class Recording(
    val file: File,
    val mount: String,
    val recordedAtUtc: ZonedDateTime,
    val sizeBytes: Long,
)

object RecordingStore {

    private val STAMP: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyyMMdd_HHmm")

    fun root(context: Context): File {
        val external = context.getExternalFilesDir(null)
        return File(external ?: context.filesDir, "atis")
    }

    /** `atis/<mount>/<mount>_20260824_1402Z.mp3`, stamped in UTC the way ATIS itself is. */
    fun fileFor(context: Context, mount: String, at: Instant): File {
        val safeMount = mount.replace(Regex("""[^A-Za-z0-9_.\-]"""), "_")
        val stamp = ZonedDateTime.ofInstant(at, ZoneOffset.UTC).format(STAMP)
        val dir = File(root(context), safeMount)
        dir.mkdirs()
        return File(dir, "${safeMount}_${stamp}Z.mp3")
    }

    /** Newest first. */
    fun list(context: Context): List<Recording> {
        val root = root(context)
        val files = root.walkTopDown()
            .maxDepth(2)
            .filter { it.isFile && it.extension.equals("mp3", ignoreCase = true) }
            .toList()
        return files
            .map { file ->
                Recording(
                    file = file,
                    mount = file.parentFile?.name ?: "",
                    recordedAtUtc = parseStamp(file.name)
                        ?: ZonedDateTime.ofInstant(Instant.ofEpochMilli(file.lastModified()), ZoneOffset.UTC),
                    sizeBytes = file.length(),
                )
            }
            .sortedByDescending { it.recordedAtUtc }
    }

    fun delete(recording: Recording): Boolean = recording.file.delete()

    /** Drops captures older than [retentionDays]; 0 keeps everything. */
    fun prune(context: Context, retentionDays: Int): Int {
        if (retentionDays <= 0) return 0
        val cutoff = System.currentTimeMillis() - retentionDays * 24L * 60L * 60L * 1000L
        var removed = 0
        list(context).forEach { recording ->
            if (recording.recordedAtUtc.toInstant().toEpochMilli() < cutoff && recording.file.delete()) {
                removed++
            }
        }
        return removed
    }

    fun shareUri(context: Context, file: File): Uri =
        FileProvider.getUriForFile(context, "${context.packageName}.files", file)

    private fun parseStamp(name: String): ZonedDateTime? {
        val match = Regex("""_(\d{8})_(\d{4})Z\.mp3$""", RegexOption.IGNORE_CASE).find(name) ?: return null
        return runCatching {
            val (date, time) = match.destructured
            ZonedDateTime.of(
                date.substring(0, 4).toInt(),
                date.substring(4, 6).toInt(),
                date.substring(6, 8).toInt(),
                time.substring(0, 2).toInt(),
                time.substring(2, 4).toInt(),
                0,
                0,
                ZoneOffset.UTC,
            )
        }.getOrNull()
    }
}
