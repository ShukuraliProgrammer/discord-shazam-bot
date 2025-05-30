import sqlite3
from datetime import datetime

# Database setup
def init_db():
    conn = sqlite3.connect('music_bot.db')
    c = conn.cursor()

    # User music history
    c.execute('''CREATE TABLE IF NOT EXISTS user_history
                 (user_id TEXT, song_title TEXT, artist TEXT, timestamp TEXT, 
                  spotify_url TEXT, youtube_url TEXT, genre TEXT, mood TEXT)''')

    # User music preferences and recommendations
    c.execute('''CREATE TABLE IF NOT EXISTS user_preferences
                 (user_id TEXT, favorite_genres TEXT, favorite_artists TEXT, 
                  mood_preferences TEXT, discovery_score INTEGER)''')

    # Community music sharing
    c.execute('''CREATE TABLE IF NOT EXISTS shared_music
                 (share_id TEXT, user_id TEXT, song_title TEXT, artist TEXT,
                  timestamp TEXT, likes INTEGER, server_id TEXT, channel_id TEXT)''')

    # Collaborative playlists
    c.execute('''CREATE TABLE IF NOT EXISTS playlists
                 (playlist_id TEXT, name TEXT, creator_id TEXT, server_id TEXT,
                  contributors TEXT, songs TEXT, created_at TEXT)''')

    conn.commit()
    conn.close()


def save_to_history(user_id, title, artist, spotify_url):
    """Save identified song to user history"""
    conn = sqlite3.connect('music_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO user_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (str(user_id), title, artist, datetime.now().isoformat(),
               spotify_url, "", "", ""))
    conn.commit()
    conn.close()
