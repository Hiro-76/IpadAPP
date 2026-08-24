package io.github.hiro76.atisgrabber

import io.github.hiro76.atisgrabber.net.LiveAtcParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LiveAtcParserTest {

    private val searchPage = """
        <html><body>
        <table>
          <tr><td><strong>Tokyo Intl Tower</strong></td>
              <td><a href="/hlisten.php?mount=rjtt_twr&icao=rjtt">Listen</a>
                  <a href="/play/rjtt_twr.pls">pls</a></td></tr>
          <tr><td><strong>Tokyo Intl ATIS</strong></td>
              <td><a href="/hlisten.php?mount=rjtt_atis&icao=rjtt">Listen</a>
                  <a href="/play/rjtt_atis.pls">pls</a></td></tr>
        </table>
        </body></html>
    """.trimIndent()

    @Test
    fun `finds every mount once, ATIS first`() {
        val feeds = LiveAtcParser.parseSearchPage(searchPage)
        assertEquals(listOf("rjtt_atis", "rjtt_twr"), feeds.map { it.mount })
        assertTrue(feeds.first().isAtis)
        assertEquals("Tokyo Intl ATIS", feeds.first().label)
    }

    @Test
    fun `mount named only in a play link still shows up`() {
        val feeds = LiveAtcParser.parseSearchPage("""<a href="/play/kjfk_atis.pls">ATIS</a>""")
        assertEquals(listOf("kjfk_atis"), feeds.map { it.mount })
    }

    @Test
    fun `reads stream urls out of a pls playlist`() {
        val pls = """
            [playlist]
            NumberOfEntries=2
            File1=https://d.liveatc.net/rjtt_atis
            Title1=RJTT ATIS
            File2=http://d2.liveatc.net/rjtt_atis
        """.trimIndent()
        assertEquals(
            listOf("https://d.liveatc.net/rjtt_atis", "http://d2.liveatc.net/rjtt_atis"),
            LiveAtcParser.parsePlaylist(pls),
        )
    }

    @Test
    fun `falls back to bare urls when the body is not a pls`() {
        assertEquals(
            listOf("https://d.liveatc.net/kjfk_atis"),
            LiveAtcParser.parsePlaylist("#EXTM3U\nhttps://d.liveatc.net/kjfk_atis\n"),
        )
    }
}
