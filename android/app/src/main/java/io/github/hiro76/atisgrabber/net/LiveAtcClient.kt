package io.github.hiro76.atisgrabber.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import java.util.concurrent.TimeUnit

/**
 * The little bit of LiveATC we talk to: the airport search page, the playlist that names a mount's
 * stream, and the stream itself. One request per capture, plus a search only when the user asks.
 */
class LiveAtcClient(
    private val http: OkHttpClient = defaultClient(),
) {

    suspend fun searchFeeds(icao: String): List<Feed> = withContext(Dispatchers.IO) {
        val code = icao.trim().uppercase()
        require(code.isNotEmpty()) { "ICAO code is empty" }
        val body = get("https://www.liveatc.net/search/?icao=$code").use { response ->
            if (!response.isSuccessful) error("search failed: HTTP ${response.code}")
            response.body?.string().orEmpty()
        }
        LiveAtcParser.parseSearchPage(body)
    }

    /**
     * Turns a mount name into the URL its audio actually comes from. The `.pls` playlist is the
     * authoritative answer; when it is unavailable the direct mount URL is the long-standing
     * fallback and is worth a try before giving up.
     */
    suspend fun resolveStreamUrl(mount: String): String = withContext(Dispatchers.IO) {
        val name = mount.trim()
        require(name.isNotEmpty()) { "mount is empty" }
        val fromPlaylist = runCatching {
            get("https://www.liveatc.net/play/$name.pls").use { response ->
                if (!response.isSuccessful) error("playlist failed: HTTP ${response.code}")
                LiveAtcParser.parsePlaylist(response.body?.string().orEmpty()).firstOrNull()
            }
        }.getOrNull()
        fromPlaylist ?: "https://d.liveatc.net/$name"
    }

    /** Opens the audio stream. The caller owns the [Response] and must close it. */
    fun openStream(url: String): Response {
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", USER_AGENT)
            .header("Icy-MetaData", "0")
            .header("Accept", "*/*")
            .build()
        return http.newBuilder()
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
            .newCall(request)
            .execute()
    }

    private fun get(url: String): Response {
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", USER_AGENT)
            .build()
        return http.newCall(request).execute()
    }

    companion object {
        const val USER_AGENT = "AtisGrabber/1.0 (Android; personal ATIS recorder)"

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .callTimeout(0, TimeUnit.MILLISECONDS)
            .retryOnConnectionFailure(true)
            .followRedirects(true)
            .followSslRedirects(true)
            .build()
    }
}
