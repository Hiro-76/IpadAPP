package io.github.hiro76.atisgrabber.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Dark = darkColorScheme(
    primary = Color(0xFF7FD1FF),
    onPrimary = Color(0xFF00344C),
    secondary = Color(0xFF9CCBFF),
    background = Color(0xFF0B1220),
    surface = Color(0xFF111B2E),
    surfaceVariant = Color(0xFF1B2740),
    error = Color(0xFFFFB4AB),
)

private val Light = lightColorScheme(
    primary = Color(0xFF0B5C8A),
    secondary = Color(0xFF2E6F9E),
    background = Color(0xFFF6F8FC),
    surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFE3E9F2),
)

@Composable
fun AtisTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) Dark else Light,
        content = content,
    )
}
