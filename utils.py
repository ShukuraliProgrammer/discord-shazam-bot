
def get_provider_color(provider):
    """Get embed color based on music provider"""
    colors = {
        "Spotify": 0x1DB954,  # Spotify Green
        "YouTube Music": 0xFF0000,  # YouTube Red
        "Yandex Music": 0xFFCC00,  # Yandex Yellow
        "Apple Music": 0x000000,  # Apple Black
        "SoundCloud": 0xFF5500,  # SoundCloud Orange
        "Not Found": 0x808080  # Gray
    }
    return colors.get(provider, 0x808080)


def get_provider_emoji(provider):
    """Get emoji for music provider"""
    emojis = {
        "Spotify": "🎧 ",
        "YouTube Music": "📺 ",
        "Yandex Music": "🎵 ",
        "Apple Music": "🍎 ",
        "SoundCloud": "☁️ ",
        "Not Found": "❌ "
    }
    return emojis.get(provider, "🎵 ")


def format_duration(duration_ms):
    """Format duration from milliseconds to MM:SS"""
    if not duration_ms:
        return "Unknown"

    seconds = int(duration_ms) // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"



# Helper functions
def get_mood_from_features(features):
    """Determine mood from Spotify audio features"""
    valence = features.get('valence', 0.5)
    #energy = features.get('energy', 0.5)
    #danceability = features.get('danceability', 0.5)

    if valence > 0.7:
        return "😄 Happy & Energetic"
    #elif valence > 0.6 and danceability > 0.7:
    #    return "🕺 Upbeat & Danceable"
    #elif valence < 0.4 and energy < 0.4:
    #    return "😢 Sad & Mellow"
    #elif energy > 0.8:
    #    return "⚡ High Energy"
    elif valence > 0.6:
        return "😊 Positive"
    else:
        return "😐 Neutral"
