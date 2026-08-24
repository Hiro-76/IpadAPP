package io.github.hiro76.atisgrabber.data

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject

/** Everything the app remembers between runs. */
data class Config(
    val icao: String = "",
    val mount: String = "",
    val label: String = "",
    val enabled: Boolean = false,
    val minuteOfHour: Int = 2,
    val secondOffset: Int = 30,
    val intervalMinutes: Int = 60,
    val captureSeconds: Int = 120,
    val retentionDays: Int = 7,
    val wifiOnly: Boolean = false,
    val useAlarmClock: Boolean = true,
    val notifyOnFinish: Boolean = true,
    val recentFeeds: List<RecentFeed> = emptyList(),
    val lastResult: String = "",
    val lastResultAt: Long = 0L,
    val lastResultOk: Boolean = false,
) {
    val hasFeed: Boolean get() = mount.isNotBlank()
}

data class RecentFeed(val mount: String, val label: String, val icao: String)

/** Config storage. Backed by SharedPreferences so alarms and services can read it without setup. */
object ConfigStore {

    private const val FILE = "atis_grabber"
    private lateinit var prefs: SharedPreferences
    private val _state = MutableStateFlow(Config())
    val state: StateFlow<Config> = _state.asStateFlow()

    @Synchronized
    fun init(context: Context) {
        if (!::prefs.isInitialized) {
            prefs = context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            _state.value = read()
        }
    }

    fun current(context: Context): Config {
        init(context)
        return _state.value
    }

    fun update(context: Context, block: (Config) -> Config): Config {
        init(context)
        val updated = block(_state.value)
        write(updated)
        _state.value = updated
        return updated
    }

    private fun read(): Config {
        val default = Config()
        return Config(
            icao = prefs.getString("icao", default.icao)!!,
            mount = prefs.getString("mount", default.mount)!!,
            label = prefs.getString("label", default.label)!!,
            enabled = prefs.getBoolean("enabled", default.enabled),
            minuteOfHour = prefs.getInt("minuteOfHour", default.minuteOfHour),
            secondOffset = prefs.getInt("secondOffset", default.secondOffset),
            intervalMinutes = prefs.getInt("intervalMinutes", default.intervalMinutes),
            captureSeconds = prefs.getInt("captureSeconds", default.captureSeconds),
            retentionDays = prefs.getInt("retentionDays", default.retentionDays),
            wifiOnly = prefs.getBoolean("wifiOnly", default.wifiOnly),
            useAlarmClock = prefs.getBoolean("useAlarmClock", default.useAlarmClock),
            notifyOnFinish = prefs.getBoolean("notifyOnFinish", default.notifyOnFinish),
            recentFeeds = decodeRecent(prefs.getString("recentFeeds", "") ?: ""),
            lastResult = prefs.getString("lastResult", default.lastResult)!!,
            lastResultAt = prefs.getLong("lastResultAt", default.lastResultAt),
            lastResultOk = prefs.getBoolean("lastResultOk", default.lastResultOk),
        )
    }

    private fun write(config: Config) {
        prefs.edit()
            .putString("icao", config.icao)
            .putString("mount", config.mount)
            .putString("label", config.label)
            .putBoolean("enabled", config.enabled)
            .putInt("minuteOfHour", config.minuteOfHour)
            .putInt("secondOffset", config.secondOffset)
            .putInt("intervalMinutes", config.intervalMinutes)
            .putInt("captureSeconds", config.captureSeconds)
            .putInt("retentionDays", config.retentionDays)
            .putBoolean("wifiOnly", config.wifiOnly)
            .putBoolean("useAlarmClock", config.useAlarmClock)
            .putBoolean("notifyOnFinish", config.notifyOnFinish)
            .putString("recentFeeds", encodeRecent(config.recentFeeds))
            .putString("lastResult", config.lastResult)
            .putLong("lastResultAt", config.lastResultAt)
            .putBoolean("lastResultOk", config.lastResultOk)
            .apply()
    }

    private fun encodeRecent(feeds: List<RecentFeed>): String {
        val array = JSONArray()
        feeds.take(8).forEach { feed ->
            array.put(
                JSONObject()
                    .put("mount", feed.mount)
                    .put("label", feed.label)
                    .put("icao", feed.icao),
            )
        }
        return array.toString()
    }

    private fun decodeRecent(raw: String): List<RecentFeed> {
        if (raw.isBlank()) return emptyList()
        return runCatching {
            val array = JSONArray(raw)
            (0 until array.length()).map { index ->
                val item = array.getJSONObject(index)
                RecentFeed(
                    mount = item.optString("mount"),
                    label = item.optString("label"),
                    icao = item.optString("icao"),
                )
            }.filter { it.mount.isNotBlank() }
        }.getOrDefault(emptyList())
    }
}
