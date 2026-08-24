package io.github.hiro76.atisgrabber.schedule

import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit

/**
 * When the next capture is due. ATIS is normally reissued on the hour, so the app waits a couple of
 * minutes past it and then records; [intervalMinutes] of 30 also catches half-hourly updates.
 */
object Schedule {

    /** Minute-of-hour offsets that must divide the hour evenly. */
    val INTERVALS = listOf(60, 30, 20, 15)

    fun nextTrigger(
        nowMillis: Long,
        minuteOfHour: Int,
        secondOffset: Int,
        intervalMinutes: Int,
        zone: ZoneId = ZoneId.systemDefault(),
    ): Long {
        val interval = if (intervalMinutes in INTERVALS) intervalMinutes else 60
        val minute = minuteOfHour.coerceIn(0, interval - 1)
        val second = secondOffset.coerceIn(0, 59)
        val now = ZonedDateTime.ofInstant(Instant.ofEpochMilli(nowMillis), zone)
        val hourStart = now.truncatedTo(ChronoUnit.HOURS)
        val slots = 60 / interval
        for (hour in 0..1) {
            for (slot in 0 until slots) {
                val candidate = hourStart
                    .plusHours(hour.toLong())
                    .plusMinutes((slot * interval + minute).toLong())
                    .plusSeconds(second.toLong())
                if (candidate.toInstant().toEpochMilli() > nowMillis) {
                    return candidate.toInstant().toEpochMilli()
                }
            }
        }
        // Unreachable in practice: the second hour of candidates always lies ahead of now.
        return hourStart.plusHours(2).toInstant().toEpochMilli()
    }
}
