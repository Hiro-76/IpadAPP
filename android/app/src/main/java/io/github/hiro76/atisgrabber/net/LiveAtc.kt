package io.github.hiro76.atisgrabber.net

/** One audio feed published by LiveATC for an airport. */
data class Feed(
    val mount: String,
    val label: String,
) {
    val isAtis: Boolean
        get() = mount.contains("atis", ignoreCase = true) || label.contains("atis", ignoreCase = true)
}

/**
 * Pulls feed mounts out of LiveATC pages.
 *
 * The pages are plain HTML meant for humans, so the parsing stays deliberately loose: it looks for
 * the two shapes a mount name always appears in (`/play/<mount>.pls` and `...mount=<mount>`) and
 * takes whatever heading sits just before it as the label. If LiveATC reshuffles its markup the
 * mounts still come out; only the labels get worse, and a mount can always be typed by hand.
 */
object LiveAtcParser {

    private val MOUNT = Regex(
        """/play/([A-Za-z0-9_.\-]+)\.pls|[?&;]mount=([A-Za-z0-9_.\-]+)""",
        RegexOption.IGNORE_CASE,
    )
    private val BOLD = Regex("""<(?:strong|b|h[1-4])[^>]*>(.*?)</(?:strong|b|h[1-4])>""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
    private val TAG = Regex("""<[^>]*>""")
    private val PLS_FILE = Regex("""(?im)^\s*File\d*\s*=\s*(\S+)\s*$""")

    /** Feeds found on an airport search page, ATIS first, duplicates removed. */
    fun parseSearchPage(html: String): List<Feed> {
        val found = LinkedHashMap<String, Feed>()
        for (match in MOUNT.findAll(html)) {
            val mount = (match.groupValues[1].takeIf { it.isNotEmpty() } ?: match.groupValues[2]).trim()
            if (mount.isEmpty() || mount.length > 64) continue
            val key = mount.lowercase()
            if (found.containsKey(key)) continue
            found[key] = Feed(mount, labelBefore(html, match.range.first) ?: mount)
        }
        return found.values.sortedByDescending { it.isAtis }
    }

    /** Stream URLs listed in a `.pls` playlist (or a bare `.m3u` style list of URLs). */
    fun parsePlaylist(body: String): List<String> {
        val fromPls = PLS_FILE.findAll(body).map { it.groupValues[1] }.toList()
        if (fromPls.isNotEmpty()) return fromPls
        return body.lineSequence()
            .map { it.trim() }
            .filter { it.startsWith("http://", true) || it.startsWith("https://", true) }
            .toList()
    }

    /** The last heading before [index]; that is where LiveATC prints the feed's name. */
    private fun labelBefore(html: String, index: Int): String? {
        val window = html.substring(maxOf(0, index - 600), index)
        val bold = BOLD.findAll(window).lastOrNull()?.groupValues?.get(1)
        val candidate = bold ?: window.substringAfterLast('>', "")
        return clean(candidate)
    }

    private fun clean(raw: String): String? {
        val text = TAG.replace(raw, " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace(Regex("""\s+"""), " ")
            .trim()
        return text.takeIf { it.isNotEmpty() && it.length <= 80 }
    }
}
