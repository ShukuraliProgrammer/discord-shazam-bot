import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

import discord
from discord.ext import commands
import aiohttp
import os
import json
import sqlite3
from datetime import datetime
import requests
import base64
import hashlib
import hmac
import time
from dotenv import load_dotenv
from collections import Counter

from recomendations import (get_mood_recommendations, get_genre_recommendations,
                            get_artist_recommendations, get_fallback_recommendations)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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


class MusicRecognitionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.acrcloud_host = 'identify-ap-southeast-1.acrcloud.com'
        self.acrcloud_access_key = os.getenv('ACRCLOUD_ACCESS_KEY')
        self.acrcloud_access_secret = os.getenv('ACRCLOUD_ACCESS_SECRET')
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')

        init_db()

    async def on_ready(self):
        print(f'{self.user} is ready to recognize music!')
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="for music to identify"))


bot = MusicRecognitionBot()


# ACRCloud integration for music recognition
def recognize_audio(audio_data):
    """Recognize audio using ACRCloud API"""
    timestamp = str(int(time.time()))
    string_to_sign = f"POST\n/v1/identify\n{bot.acrcloud_access_key}\naudio\n1\n{timestamp}"
    signature = base64.b64encode(
        hmac.new(
            bot.acrcloud_access_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
    ).decode('utf-8')

    files = {'sample': audio_data}
    data = {
        'access_key': bot.acrcloud_access_key,
        'sample_bytes': len(audio_data),
        'timestamp': timestamp,
        'signature': signature,
        'data_type': 'audio',
        'signature_version': '1'
    }

    response = requests.post(f'http://{bot.acrcloud_host}/v1/identify', files=files, data=data)
    return response.json()


# Spotify integration
async def get_spotify_token():
    """Get Spotify access token"""
    auth_string = f"{bot.spotify_client_id}:{bot.spotify_client_secret}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            json_result = await response.json()
            return json_result["access_token"]


async def get_song_analysis(track_id):
    """Get detailed Spotify audio analysis"""
    token = await get_spotify_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        # Get audio features
        async with session.get(f"https://api.spotify.com/v1/audio-features/{track_id}", headers=headers) as response:
            features = await response.json()

        # Get audio analysis
        async with session.get(f"https://api.spotify.com/v1/audio-analysis/{track_id}", headers=headers) as response:
            analysis = await response.json()

    return features, analysis

@bot.event
async def on_ready():
    await bot.tree.sync()

# Music recognition command
@bot.command(name='identify')
async def identify_music(ctx):
    """Identify music from audio file or voice channel"""
    if ctx.message.attachments:
        # Process audio file attachment
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith(('.mp3', '.wav', '.m4a', '.flac')):
            await ctx.send("❌ Please upload an audio file (mp3, wav, m4a, flac)")
            return

        audio_data = await attachment.read()

        # Show processing message
        processing_msg = await ctx.send("🎵 Analyzing audio... This may take a moment!")

        try:
            # Recognize the music
            result = recognize_audio(audio_data)

            if result['status']['code'] == 0:
                music = result['metadata']['music'][0]
                title = music['title']
                artist = music['artists'][0]['name']
                album = music.get('album', {}).get('name', 'Unknown Album')
                release_date = music.get('release_date', 'Unknown')
                print("Title: ", title, artist)
                # Get additional info from Spotify
                spotify_info = await search_spotify(f"{title} {artist}")

                # Create rich embed
                embed = discord.Embed(
                    title="🎵 Song Identified!",
                    description=f"**{title}** by **{artist}**",
                    color=0x1DB954
                )
                embed.add_field(name="Album", value=album, inline=True)
                embed.add_field(name="Release Date", value=release_date, inline=True)

                if spotify_info:
                    embed.add_field(name="Popularity", value=f"{spotify_info.get('popularity', 0)}/100", inline=True)
                    embed.add_field(name="Preview",
                                    value="[Listen on Spotify](https://open.spotify.com/track/" + spotify_info[
                                        'id'] + ")", inline=False)

                    # Add audio features
                    features, analysis = await get_song_analysis(spotify_info['id'])
                    if features:
                        mood = get_mood_from_features(features)
                        embed.add_field(name="Mood", value=mood, inline=True)
                        #embed.add_field(name="Danceability", value=f"{features['danceability']:.1%}", inline=True)
                        #embed.add_field(name="Energy", value=f"{features['energy']:.1%}", inline=True)

                # Save to user history
                save_to_history(ctx.author.id, title, artist, spotify_info.get('external_urls', {}).get('spotify', ''))

                # Add reaction buttons
                await processing_msg.edit(content="", embed=embed)
                await processing_msg.add_reaction("❤️")  # Like
                await processing_msg.add_reaction("💾")  # Save to playlist
                await processing_msg.add_reaction("🔄")  # Get recommendations

            else:
                await processing_msg.edit(content="❌ Sorry, I couldn't identify this song. Try a clearer audio sample!")

        except Exception as e:
            await processing_msg.edit(content=f"❌ Error processing audio: {str(e)}")

    else:
        await ctx.send("🎤 Please upload an audio file or use `!listen` to identify from voice channel")


# Advanced recommendation system
@bot.command(name='recommend')
async def get_recommendations(ctx, *, mood_or_genre=None):
    """Get personalized music recommendations"""
    user_id = str(ctx.author.id)

    # Get user's music history
    conn = sqlite3.connect('music_bot.db')
    c = conn.cursor()
    c.execute("SELECT song_title, artist, genre FROM user_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20",
              (user_id,))
    history = c.fetchall()
    conn.close()

    if not history:
        await ctx.send("🎵 I need to learn your music taste first! Use `!identify` on some songs.")
        return

    # Generate recommendations based on history and mood
    recommendations = await generate_smart_recommendations(history, mood_or_genre)

    embed = discord.Embed(
        title="🎯 Personalized Recommendations",
        description=f"Based on your music taste" + (f" and '{mood_or_genre}' mood" if mood_or_genre else ""),
        color=0xFF6B6B
    )

    for i, rec in enumerate(recommendations[:5], 1):
        embed.add_field(
            name=f"{i}. {rec['title']} - {rec['artist']}",
            value=f"Match: {rec['match_score']}% | [Listen]({rec['spotify_url']})",
            inline=False
        )

    await ctx.send(embed=embed)


# Collaborative playlist feature
@bot.command(name='playlist')
async def playlist_commands(ctx, action=None, *, args=None):
    """Manage collaborative playlists"""
    if action == "create":
        if not args:
            await ctx.send("Usage: `!playlist create <playlist_name>`")
            return

        playlist_id = f"{ctx.guild.id}_{int(time.time())}"
        conn = sqlite3.connect('music_bot.db')
        c = conn.cursor()
        c.execute("INSERT INTO playlists VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (playlist_id, args, str(ctx.author.id), str(ctx.guild.id),
                   json.dumps([str(ctx.author.id)]), json.dumps([]),
                   datetime.now().isoformat()))
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🎵 Playlist Created!",
            description=f"**{args}** is ready for collaboration!",
            color=0x00FF7F
        )
        embed.add_field(name="Creator", value=ctx.author.mention, inline=True)
        embed.add_field(name="ID", value=playlist_id, inline=True)
        embed.add_field(name="Usage", value=f"`!playlist add {playlist_id} <song_name>`", inline=False)

        await ctx.send(embed=embed)

    elif action == "list":
        conn = sqlite3.connect('music_bot.db')
        c = conn.cursor()
        c.execute("SELECT playlist_id, name, creator_id FROM playlists WHERE server_id = ?", (str(ctx.guild.id),))
        playlists = c.fetchall()
        conn.close()

        if not playlists:
            await ctx.send("🎵 No playlists found. Create one with `!playlist create <name>`")
            return

        embed = discord.Embed(title="🎵 Server Playlists", color=0x9370DB)
        for playlist_id, name, creator_id in playlists:
            user = bot.get_user(int(creator_id))
            embed.add_field(
                name=name,
                value=f"ID: `{playlist_id}`\nCreator: {user.mention if user else 'Unknown'}",
                inline=True
            )

        await ctx.send(embed=embed)


# Music sharing and social features
@bot.command(name='share')
async def share_music(ctx, *, song_info=None):
    """Share music with the community"""
    if not song_info:
        await ctx.send("Usage: `!share <song_name> - <artist>`")
        return

    share_id = f"{ctx.guild.id}_{int(time.time())}"

    try:
        title, artist = song_info.split(' - ', 1)

        conn = sqlite3.connect('music_bot.db')
        c = conn.cursor()
        c.execute("INSERT INTO shared_music VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (share_id, str(ctx.author.id), title.strip(), artist.strip(),
                   datetime.now().isoformat(), 0, str(ctx.guild.id), str(ctx.channel.id)))
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🎵 Music Shared!",
            description=f"**{title}** by **{artist}**",
            color=0xFF69B4
        )
        embed.add_field(name="Shared by", value=ctx.author.mention, inline=True)
        embed.set_footer(text="React with ❤️ to like this share!")

        message = await ctx.send(embed=embed)
        await message.add_reaction("❤️")

    except ValueError:
        await ctx.send("❌ Please use format: `!share <song_name> - <artist>`")


# Music analytics and insights
@bot.command(name='stats')
async def music_stats(ctx, user: discord.Member = None):
    """Show music listening statistics"""
    target_user = user or ctx.author
    user_id = str(target_user.id)

    conn = sqlite3.connect('music_bot.db')
    c = conn.cursor()

    # Get listening stats
    c.execute("SELECT COUNT(*) FROM user_history WHERE user_id = ?", (user_id,))
    total_songs = c.fetchone()[0]

    c.execute(
        "SELECT artist, COUNT(*) as count FROM user_history WHERE user_id = ? GROUP BY artist ORDER BY count DESC LIMIT 5",
        (user_id,))
    top_artists = c.fetchall()

    c.execute(
        "SELECT genre, COUNT(*) as count FROM user_history WHERE user_id = ? GROUP BY genre ORDER BY count DESC LIMIT 3",
        (user_id,))
    top_genres = c.fetchall()

    conn.close()

    embed = discord.Embed(
        title=f"🎵 Music Stats for {target_user.display_name}",
        color=0x1E90FF
    )
    embed.add_field(name="Total Songs Identified", value=total_songs, inline=True)

    if top_artists:
        artists_text = "\n".join(
            [f"{i + 1}. {artist} ({count} songs)" for i, (artist, count) in enumerate(top_artists)])
        embed.add_field(name="Top Artists", value=artists_text, inline=False)

    if top_genres:
        genres_text = "\n".join([f"{genre}: {count}" for genre, count in top_genres])
        embed.add_field(name="Favorite Genres", value=genres_text, inline=True)

    embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else None)

    await ctx.send(embed=embed)


# Mood-based music discovery
@bot.command(name='mood')
async def mood_music(ctx, *, mood=None):
    """Get music recommendations based on mood"""
    if not mood:
        await ctx.send("🎭 Available moods: happy, sad, energetic, chill, romantic, focus, party, workout")
        return

    mood_keywords = {
        'happy': ['upbeat', 'cheerful', 'positive', 'uplifting'],
        'sad': ['melancholy', 'emotional', 'slow', 'thoughtful'],
        'energetic': ['high-energy', 'pump-up', 'intense', 'powerful'],
        'chill': ['relaxing', 'calm', 'ambient', 'peaceful'],
        'romantic': ['love', 'romantic', 'intimate', 'soulful'],
        'focus': ['instrumental', 'ambient', 'concentration', 'study'],
        'party': ['dance', 'electronic', 'club', 'celebration'],
        'workout': ['motivation', 'high-tempo', 'intense', 'fitness']
    }

    if mood.lower() not in mood_keywords:
        await ctx.send("❌ Unknown mood. Try: happy, sad, energetic, chill, romantic, focus, party, workout")
        return

    # Here you would integrate with music APIs to get mood-based recommendations
    embed = discord.Embed(
        title=f"🎭 {mood.title()} Music",
        description=f"Perfect songs for when you're feeling {mood}",
        color=0xFFD700
    )

    # This would be replaced with actual API calls
    embed.add_field(name="Coming Soon!", value="Mood-based recommendations will be available soon!", inline=False)

    await ctx.send(embed=embed)
#
# from discord.ext import audiorec
#
# @bot.command(name='listen')
# async def listen_to_voice(ctx):
#     """Listen to voice channel and identify playing music"""
#     if not ctx.author.voice:
#         await ctx.send("❌ You need to be in a voice channel!")
#         return
#
#     channel = ctx.author.voice.channel
#     vc = await channel.connect()
#
#     # Record audio from voice channel
#     audio_sink = AudioSink()
#     vc.start_recording(audio_sink, finished_callback)
#
#     await ctx.send("🎧 Listening to voice channel... Say 'stop' to end recording")
#
#     # Wait for stop command or timeout
#     await asyncio.sleep(10)  # 10 second sample
#     vc.stop_recording()
#     await vc.disconnect()
#
#     # Process recorded audio
#     if audio_sink.audio_data:
#         result = recognize_audio(audio_sink.audio_data)
#         print("Result: ", result)



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


def save_to_history(user_id, title, artist, spotify_url):
    """Save identified song to user history"""
    conn = sqlite3.connect('music_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO user_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (str(user_id), title, artist, datetime.now().isoformat(),
               spotify_url, "", "", ""))
    conn.commit()
    conn.close()


async def search_spotify(query):
    """Search for a song on Spotify"""
    token = await get_spotify_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.spotify.com/v1/search?q={query}&type=track&limit=1",
                               headers=headers) as response:
            data = await response.json()
            if data['tracks']['items']:
                return data['tracks']['items'][0]
    return None



async def generate_smart_recommendations(history, mood=None):
    """Generate smart recommendations based on user history"""
    recommendations = []

    if not history:
        return recommendations

    # Analyze user's music patterns
    artists = [item[1] for item in history]
    genres = [item[2] for item in history if item[2]]

    # Get most frequent artists and genres
    artist_counts = Counter(artists)
    genre_counts = Counter(genres) if genres else Counter()

    # Get top artists (limit to avoid API overuse)
    top_artists = [artist for artist, count in artist_counts.most_common(5)]
    top_genres = [genre for genre, count in genre_counts.most_common(3)] if genres else []

    try:
        # Get Spotify token
        token = await get_spotify_token()
        if not token:
            return get_fallback_recommendations(top_artists, mood)

        # Strategy 1: Get recommendations based on top artists
        for artist in top_artists[:3]:  # Limit to top 3 artists
            artist_recs = await get_artist_recommendations(artist, token)
            recommendations.extend(artist_recs)

        # Strategy 2: Get genre-based recommendations if we have genres
        if top_genres:
            genre_recs = await get_genre_recommendations(top_genres, token, mood)
            recommendations.extend(genre_recs)

        # Strategy 3: Get mood-based recommendations
        if mood:
            mood_recs = await get_mood_recommendations(mood, token, top_artists)
            recommendations.extend(mood_recs)

        # Remove duplicates and limit results
        seen_tracks = set()
        unique_recommendations = []

        for rec in recommendations:
            track_key = f"{rec['title']}_{rec['artist']}"
            if track_key not in seen_tracks:
                seen_tracks.add(track_key)
                unique_recommendations.append(rec)

        # Sort by match score and return top 10
        unique_recommendations.sort(key=lambda x: x['match_score'], reverse=True)
        return unique_recommendations[:10]

    except Exception as e:
        print(f"Error generating recommendations: {e}")
        return get_fallback_recommendations(top_artists, mood)

# Event handlers for reactions
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if str(reaction.emoji) == "❤️":
        # Handle like reaction on shared music
        embed = reaction.message.embeds[0] if reaction.message.embeds else None
        if embed and "Music Shared!" in embed.title:
            # Update like count in database
            conn = sqlite3.connect('music_bot.db')
            c = conn.cursor()
            c.execute("UPDATE shared_music SET likes = likes + 1 WHERE timestamp = ?",
                      (datetime.now().date().isoformat(),))
            conn.commit()
            conn.close()



# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)

