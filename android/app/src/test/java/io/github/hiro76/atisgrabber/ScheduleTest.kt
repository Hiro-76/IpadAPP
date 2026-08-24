package io.github.hiro76.atisgrabber

import io.github.hiro76.atisgrabber.schedule.Schedule
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

class ScheduleTest {

    private val tokyo = ZoneId.of("Asia/Tokyo")

    private fun at(text: String): Long = ZonedDateTime.parse(text).toInstant().toEpochMilli()

    private fun next(now: String, minute: Int = 2, second: Int = 30, interval: Int = 60): String =
        ZonedDateTime.ofInstant(
            java.time.Instant.ofEpochMilli(
                Schedule.nextTrigger(at(now), minute, second, interval, tokyo),
            ),
            tokyo,
        ).toString()

    @Test
    fun `waits for two minutes past the coming hour`() {
        assertEquals("2026-08-24T15:02:30+09:00[Asia/Tokyo]", next("2026-08-24T14:40:00+09:00"))
    }

    @Test
    fun `a firing at the trigger moves on to the next hour`() {
        assertEquals("2026-08-24T16:02:30+09:00[Asia/Tokyo]", next("2026-08-24T15:02:30+09:00"))
    }

    @Test
    fun `half hourly catches both slots`() {
        assertEquals(
            "2026-08-24T15:32:30+09:00[Asia/Tokyo]",
            next("2026-08-24T15:10:00+09:00", interval = 30),
        )
        assertEquals(
            "2026-08-24T16:02:30+09:00[Asia/Tokyo]",
            next("2026-08-24T15:40:00+09:00", interval = 30),
        )
    }

    @Test
    fun `a minute past the interval is pulled back into range`() {
        assertEquals(
            "2026-08-24T15:29+09:00[Asia/Tokyo]",
            next("2026-08-24T15:10:00+09:00", minute = 45, second = 0, interval = 30),
        )
    }
}
