package io.github.hiro76.atisgrabber.ui

import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

private val LOCAL_FULL = DateTimeFormatter.ofPattern("M/d HH:mm:ss")
private val LOCAL_SHORT = DateTimeFormatter.ofPattern("M/d HH:mm")
private val UTC_SHORT = DateTimeFormatter.ofPattern("HHmm")
private val UTC_DAY = DateTimeFormatter.ofPattern("M/d HHmm")

fun formatLocalWithUtc(millis: Long): String {
    val local = ZonedDateTime.ofInstant(Instant.ofEpochMilli(millis), ZoneId.systemDefault())
    val utc = local.withZoneSameInstant(ZoneOffset.UTC)
    return "${local.format(LOCAL_FULL)}  (${utc.format(UTC_SHORT)}Z)"
}

fun formatLocalShort(millis: Long): String =
    ZonedDateTime.ofInstant(Instant.ofEpochMilli(millis), ZoneId.systemDefault()).format(LOCAL_SHORT)

fun formatUtcDay(time: ZonedDateTime): String = time.withZoneSameInstant(ZoneOffset.UTC).format(UTC_DAY) + "Z"

fun formatCountdown(millisUntil: Long): String {
    if (millisUntil <= 0) return "まもなく"
    val total = millisUntil / 1000
    val hours = total / 3600
    val minutes = (total % 3600) / 60
    val seconds = total % 60
    return when {
        hours > 0 -> "あと ${hours}時間${minutes}分"
        minutes > 0 -> "あと ${minutes}分${seconds}秒"
        else -> "あと ${seconds}秒"
    }
}

fun formatSize(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> String.format("%.1f MB", bytes / 1024.0 / 1024.0)
    else -> "${bytes / 1024} KB"
}
