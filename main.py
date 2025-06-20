import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

import discord
import os
import json
import sqlite3
from datetime import datetime
import time
from dotenv import load_dotenv
from recomendations import generate_smart_recommendations

from settings import MusicRecognitionBot
from audio_recognition import recognize_audio
from utils import get_provider_color, get_provider_emoji, format_duration, get_mood_from_features
from providers.spotify import search_spotify, get_song_analysis
from providers.yandex import search_yandex_music
from providers.youtube import search_youtube_music
from providers.apple import search_apple_music
from parser import parse_search_query
from searches import search_all_platforms

from db import save_to_history


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


bot = MusicRecognitionBot()


@bot.event
async def on_ready():
    await bot.tree.sync()


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

                # Search across multiple providers
                music_info, provider_used = await search_multiple_providers(f"{title} {artist}")

                # Create rich embed
                embed = discord.Embed(
                    title="🎵 Song Identified!",
                    description=f"**{title}** by **{artist}**",
                    color=get_provider_color(provider_used)
                )
                embed.add_field(name="Album", value=album, inline=True)
                embed.add_field(name="Release Date", value=release_date, inline=True)
                embed.add_field(name="Found on", value=get_provider_emoji(provider_used) + provider_used, inline=True)

                if music_info:
                    # Add provider-specific information
                    if provider_used == "Spotify":
                        embed.add_field(name="Popularity", value=f"{music_info.get('popularity', 0)}/100", inline=True)
                        embed.add_field(name="Listen",
                                        value=f"[🎧 Spotify](https://open.spotify.com/track/{music_info['id']})",
                                        inline=False)

                        # Add audio features for Spotify
                        features, analysis = await get_song_analysis(music_info['id'])
                        if features:
                            mood = get_mood_from_features(features)
                            embed.add_field(name="Mood", value=mood, inline=True)

                    elif provider_used == "YouTube Music":
                        embed.add_field(name="Duration", value=format_duration(music_info.get('duration', 0)),
                                        inline=True)
                        if 'videoId' in music_info['id']:
                            embed.add_field(name="Listen",
                                            value=f"[📺 YouTube](https://youtube.com/watch?v={music_info['id']['videoId']})",
                                            inline=False)

                    elif provider_used == "Yandex Music":
                        embed.add_field(name="Duration", value=format_duration(music_info.get('durationMs', 0)),
                                        inline=True)
                        if 'id' in music_info:
                            embed.add_field(name="Listen",
                                            value=f"[🎵 Yandex Music](https://music.yandex.ru/album/{music_info.get('albums', [{}])[0].get('id', '')}/track/{music_info['id']})",
                                            inline=False)

                    elif provider_used == "Apple Music":
                        embed.add_field(name="Genre", value=music_info.get('primaryGenreName', 'Unknown'), inline=True)
                        if 'trackViewUrl' in music_info:
                            embed.add_field(name="Listen",
                                            value=f"[🍎 Apple Music]({music_info['trackViewUrl']})",
                                            inline=False)

                    elif provider_used == "SoundCloud":
                        embed.add_field(name="Plays", value=f"{music_info.get('playback_count', 0):,}", inline=True)
                        if 'permalink_url' in music_info:
                            embed.add_field(name="Listen",
                                            value=f"[☁️ SoundCloud]({music_info['permalink_url']})",
                                            inline=False)

                else:
                    embed.add_field(name="Status", value="❌ Not found on any music platform", inline=False)

                # Save to user history with provider info
                save_to_history(ctx.author.id, title, artist,
                                music_info.get(' c', {}).get('spotify',
                                                                        '') if provider_used == "Spotify" else "")

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


async def search_multiple_providers(query):
    """Search across multiple music providers in order of preference"""
    providers = [
        ("Yandex Music", search_yandex_music),
        ("Spotify", search_spotify),
        ("Apple Music", search_apple_music),
        ("YouTube Music", search_youtube_music)
    ]

    for provider_name, search_func in providers:
        try:
            result = await search_func(query)
            if result:
                print(f"✅ Found on {provider_name}: {query}")
                return result, provider_name
        except Exception as e:
            print(f"❌ Failed to search {provider_name}: {e}")
            continue

    print(f"❌ Song not found on any provider: {query}")
    return None, "Not Found"




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


@bot.command(name='search')
async def search_music(ctx, *, query):
    """
    Search for music across multiple platforms
    Usage:
    !search song:"Song Name" artist:"Artist Name" year:2023
    !search song:"Bohemian Rhapsody" artist:"Queen" platform:spotify
    !search song:"Shape of You" platform:"youtube"

    Supported platforms: spotify, youtube, yandex
    """

    # Parse the search query
    search_params = parse_search_query(query)

    if not search_params.get('song'):
        await ctx.send(
            "❌ Please provide at least a song name. Example: `!search song:\"Bohemian Rhapsody\" artist:\"Queen\"`")
        return

    # Create loading message
    loading_embed = discord.Embed(
        title="🔍 Searching...",
        description="Finding matches across platforms...",
        color=0x3498db
    )
    message = await ctx.send(embed=loading_embed)

    try:
        # Search across multiple platforms
        search_results = await search_all_platforms(search_params)

        if not search_results:
            error_embed = discord.Embed(
                title="❌ No Results Found",
                description="Couldn't find any matches for your search.",
                color=0xe74c3c
            )
            await message.edit(embed=error_embed)
            return

        # Create results embed
        results_embed = discord.Embed(
            title="🎵 Search Results",
            description=f"Found {len(search_results)} matches",
            color=0x1DB954
        )

        # Add search query info
        query_info = []
        if search_params.get('song'):
            query_info.append(f"**Song:** {search_params['song']}")
        if search_params.get('artist'):
            query_info.append(f"**Artist:** {search_params['artist']}")
        if search_params.get('year'):
            query_info.append(f"**Year:** {search_params['year']}")
        if search_params.get('platform'):
            platform_emoji = {
                'spotify': '🎵',
                'youtube': '📺',
                'yandex': '🎶'
            }
            emoji = platform_emoji.get(search_params['platform'], '🎧')
            query_info.append(f"**Platform:** {emoji} {search_params['platform'].title()}")

        results_embed.add_field(
            name="Search Query",
            value="\n".join(query_info),
            inline=False
        )

        # Add results
        for i, result in enumerate(search_results[:5], 1):  # Limit to 5 results
            links = []
            if result.get('spotify_url'):
                links.append(f"[Spotify]({result['spotify_url']})")
            if result.get('youtube_url'):
                links.append(f"[YouTube]({result['youtube_url']})")
            if result.get('yandex_url'):
                links.append(f"[Yandex Music]({result['yandex_url']})")

            # Show platform source with emoji
            platform_info = ""
            if result.get('source_platform'):
                platform_emojis = {
                    'spotify': '🎵',
                    'youtube': '📺',
                    'yandex': '🎶'
                }
                emoji = platform_emojis.get(result['source_platform'], '🎧')
                platform_info = f"{emoji} "

            result_info = []
            if result.get('album'):
                result_info.append(f"Album: {result['album']}")
            if result.get('year'):
                result_info.append(f"Year: {result['year']}")
            if result.get('duration'):
                result_info.append(f"Duration: {result['duration']}")

            field_value = ""
            if result_info:
                field_value += " • ".join(result_info) + "\n"
            if links:
                field_value += " | ".join(links)
            else:
                field_value += "No direct links available"

            results_embed.add_field(
                name=f"{platform_info}{i}. {result['title']} - {result['artist']}",
                value=field_value,
                inline=False
            )

        # Add footer
        results_embed.set_footer(text="🎧 Click the links to listen on your preferred platform")

        await message.edit(embed=results_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Search Error",
            description="An error occurred while searching. Please try again.",
            color=0xe74c3c
        )
        await message.edit(embed=error_embed)
        print(f"Search error: {e}")

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


@bot.command(name='helpp')
async def help_command(ctx, command=None):
    """Display all available commands or detailed help for a specific command"""

    if command:
        # Detailed help for specific commands
        command_help = {
            'identify': {
                'title': '🎵 Identify Music',
                'description': 'Identify music from an audio file',
                'usage': '/identify [attach audio file]',
                'example': 'Upload an audio file and use /identify to get song details'
            },
            'recommend': {
                'title': '🎯 Personal Recommendations',
                'description': 'Get personalized music recommendations based on your listening history',
                'usage': '/recommend',
                'example': '/recommend'
            },
            'playlist': {
                'title': '📝 Playlist Management',
                'description': 'Manage your playlists',
                'usage': '/playlist [list|create] [playlist_name]',
                'example': '/playlist list\n/playlist create "My Favorites"'
            },
            'share': {
                'title': '📤 Share Music',
                'description': 'Share music with other users',
                'usage': '/share [song/playlist]',
                'example': '/share "Song Name - Artist"'
            },
            'stats': {
                'title': '📊 Analytics',
                'description': 'View your music listening analytics and history',
                'usage': '/stats',
                'example': '/stats'
            },
            'mood': {
                'title': '🎭 Mood Music',
                'description': 'Get music recommendations based on your current mood',
                'usage': '/mood [mood_type]',
                'example': '/mood happy\n/mood chill'
            },
            'search': {
                'title': '🔍 Search Music',
                'description': 'Search for music by song name, artist, and platform',
                'usage': '/search [song_name] [artist] [platform]',
                'example': '/search "Bohemian Rhapsody" "Queen" spotify'
            }
        }

        if command.lower() in command_help:
            cmd_info = command_help[command.lower()]
            embed = discord.Embed(
                title=cmd_info['title'],
                description=cmd_info['description'],
                color=0x1DB954  # Spotify green
            )
            embed.add_field(name="Usage", value=f"`{cmd_info['usage']}`", inline=False)
            embed.add_field(name="Example", value=f"`{cmd_info['example']}`", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Command not found. Use `/help` to see all available commands.")
        return

    # General help - show all commands
    embed = discord.Embed(
        title="🎵 Music Bot - Available Commands",
        description="Here are all the commands you can use:",
        color=0x1DB954
    )

    # Music Discovery
    embed.add_field(
        name="🎵 Music Discovery",
        value="`/identify` - Identify music from audio file\n"
              "`/search` - Search music by name, artist, platform\n"
              "`/mood` - Get music based on your mood",
        inline=False
    )

    # Personal Features
    embed.add_field(
        name="🎯 Personal Features",
        value="`/recommend` - Get personalized recommendations\n"
              "`/stats` - View your listening analytics",
        inline=False
    )

    # Playlist Management
    embed.add_field(
        name="📝 Playlist Management",
        value="`/playlist list` - Show all your playlists\n"
              "`/playlist create` - Create a new playlist",
        inline=False
    )

    # Social Features
    embed.add_field(
        name="📤 Social Features",
        value="`/share` - Share music with other users",
        inline=False
    )

    embed.add_field(
        name="💡 Need More Help?",
        value="Use `/help [command]` for detailed information about a specific command\n"
              "Example: `/help mood` or `/help search`",
        inline=False
    )

    embed.set_footer(text="🎶 Enjoy discovering music!")

    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)

