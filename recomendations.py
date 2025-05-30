
import aiohttp
import random
from providers.spotify import get_spotify_token
from collections import Counter

async def get_artist_recommendations(artist_name, token):
    """Get recommendations based on similar artists"""
    recommendations = []

    try:
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            # First, search for the artist
            search_url = f"https://api.spotify.com/v1/search?q={artist_name.replace(' ', '%20')}&type=artist&limit=1"

            async with session.get(search_url, headers=headers) as response:
                if response.status == 200:
                    search_data = await response.json()
                    artists = search_data.get('artists', {}).get('items', [])

                    if artists:
                        artist_id = artists[0]['id']

                        # Get artist's top tracks
                        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?market=US"
                        async with session.get(top_tracks_url, headers=headers) as tracks_response:
                            if tracks_response.status == 200:
                                tracks_data = await tracks_response.json()
                                tracks = tracks_data.get('tracks', [])

                                # Convert to our format
                                for track in tracks[:3]:  # Top 3 tracks
                                    recommendations.append({
                                        'title': track['name'],
                                        'artist': track['artists'][0]['name'],
                                        'match_score': 80 + random.randint(-10, 15),  # 70-95 range
                                        'spotify_url': track['external_urls']['spotify'],
                                        'reason': f"Popular track by {artist_name}"
                                    })

                        # Get related artists and their tracks
                        related_url = f"https://api.spotify.com/v1/artists/{artist_id}/related-artists"
                        async with session.get(related_url, headers=headers) as related_response:
                            if related_response.status == 200:
                                related_data = await related_response.json()
                                related_artists = related_data.get('artists', [])

                                # Get top track from each related artist
                                for related_artist in related_artists[:2]:  # Top 2 related artists
                                    related_tracks_url = f"https://api.spotify.com/v1/artists/{related_artist['id']}/top-tracks?market=US"
                                    async with session.get(related_tracks_url, headers=headers) as rel_tracks_response:
                                        if rel_tracks_response.status == 200:
                                            rel_tracks_data = await rel_tracks_response.json()
                                            rel_tracks = rel_tracks_data.get('tracks', [])

                                            if rel_tracks:
                                                track = rel_tracks[0]  # Top track
                                                recommendations.append({
                                                    'title': track['name'],
                                                    'artist': track['artists'][0]['name'],
                                                    'match_score': 70 + random.randint(-5, 15),  # 65-85 range
                                                    'spotify_url': track['external_urls']['spotify'],
                                                    'reason': f"Similar to {artist_name}"
                                                })

    except Exception as e:
        print(f"Error getting artist recommendations for {artist_name}: {e}")

    return recommendations


async def get_genre_recommendations(genres, token, mood=None):
    """Get recommendations based on genres"""
    recommendations = []

    try:
        headers = {"Authorization": f"Bearer {token}"}

        # Map genres to Spotify seed genres (Spotify has specific genre seeds)
        spotify_genres = map_to_spotify_genres(genres)

        if spotify_genres:
            # Build recommendation parameters
            params = {
                'seed_genres': ','.join(spotify_genres[:3]),  # Max 3 seed genres
                'limit': 10,
                'market': 'US'
            }

            # Add mood-based audio features
            if mood:
                mood_features = get_mood_features(mood)
                params.update(mood_features)

            # Build URL with parameters
            param_string = '&'.join([f'{k}={v}' for k, v in params.items()])
            rec_url = f"https://api.spotify.com/v1/recommendations?{param_string}"

            async with aiohttp.ClientSession() as session:
                async with session.get(rec_url, headers=headers) as response:
                    if response.status == 200:
                        rec_data = await response.json()
                        tracks = rec_data.get('tracks', [])

                        for track in tracks:
                            recommendations.append({
                                'title': track['name'],
                                'artist': track['artists'][0]['name'],
                                'match_score': 75 + random.randint(-10, 20),  # 65-95 range
                                'spotify_url': track['external_urls']['spotify'],
                                'reason': f"Based on {', '.join(genres)} genres"
                            })

    except Exception as e:
        print(f"Error getting genre recommendations: {e}")

    return recommendations


async def get_mood_recommendations(mood, token, top_artists=None):
    """Get mood-based recommendations"""
    recommendations = []

    try:
        headers = {"Authorization": f"Bearer {token}"}

        # Get mood features
        mood_features = get_mood_features(mood)

        # Build parameters
        params = {
            'limit': 8,
            'market': 'US'
        }
        params.update(mood_features)

        # Add artist seed if available
        if top_artists:
            # Search for artist ID
            search_url = f"https://api.spotify.com/v1/search?q={top_artists[0].replace(' ', '%20')}&type=artist&limit=1"

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers) as search_response:
                    if search_response.status == 200:
                        search_data = await search_response.json()
                        artists = search_data.get('artists', {}).get('items', [])
                        if artists:
                            params['seed_artists'] = artists[0]['id']

        # If no artist seed, use popular genres for the mood
        if 'seed_artists' not in params:
            mood_genres = get_mood_genres(mood)
            params['seed_genres'] = ','.join(mood_genres[:2])

        # Build URL
        param_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        rec_url = f"https://api.spotify.com/v1/recommendations?{param_string}"

        async with aiohttp.ClientSession() as session:
            async with session.get(rec_url, headers=headers) as response:
                if response.status == 200:
                    rec_data = await response.json()
                    tracks = rec_data.get('tracks', [])

                    for track in tracks:
                        recommendations.append({
                            'title': track['name'],
                            'artist': track['artists'][0]['name'],
                            'match_score': 85 + random.randint(-10, 10),  # 75-95 range
                            'spotify_url': track['external_urls']['spotify'],
                            'reason': f"Perfect for {mood} mood"
                        })

    except Exception as e:
        print(f"Error getting mood recommendations: {e}")

    return recommendations


def map_to_spotify_genres(genres):
    """Map user genres to Spotify seed genres"""
    # Spotify has specific genre seeds - map common genres
    genre_mapping = {
        'pop': 'pop',
        'rock': 'rock',
        'hip-hop': 'hip-hop',
        'rap': 'hip-hop',
        'country': 'country',
        'jazz': 'jazz',
        'blues': 'blues',
        'classical': 'classical',
        'electronic': 'electronic',
        'dance': 'dance',
        'r&b': 'r-n-b',
        'soul': 'soul',
        'reggae': 'reggae',
        'metal': 'metal',
        'punk': 'punk',
        'indie': 'indie',
        'alternative': 'alternative',
        'folk': 'folk',
        'acoustic': 'acoustic'
    }

    spotify_genres = []
    for genre in genres:
        genre_lower = genre.lower()
        for key, value in genre_mapping.items():
            if key in genre_lower:
                spotify_genres.append(value)
                break

    return list(set(spotify_genres))  # Remove duplicates


def get_mood_features(mood):
    """Get Spotify audio features for different moods"""
    mood_features = {
        'happy': {'target_valence': 0.8, 'target_energy': 0.7, 'target_danceability': 0.6},
        'sad': {'target_valence': 0.2, 'target_energy': 0.3, 'min_acousticness': 0.3},
        'energetic': {'target_energy': 0.9, 'target_danceability': 0.8, 'min_tempo': 120},
        'chill': {'target_valence': 0.5, 'target_energy': 0.4, 'max_loudness': -8},
        'romantic': {'target_valence': 0.6, 'target_energy': 0.4, 'min_acousticness': 0.2},
        'focus': {'max_valence': 0.6, 'max_energy': 0.5, 'min_instrumentalness': 0.3},
        'party': {'target_energy': 0.9, 'target_danceability': 0.9, 'min_tempo': 120},
        'workout': {'target_energy': 0.95, 'min_tempo': 130, 'target_danceability': 0.7}
    }

    return mood_features.get(mood.lower(), {})


def get_mood_genres(mood):
    """Get appropriate genres for different moods"""
    mood_genres = {
        'happy': ['pop', 'dance'],
        'sad': ['blues', 'folk'],
        'energetic': ['electronic', 'rock'],
        'chill': ['indie', 'alternative'],
        'romantic': ['r-n-b', 'soul'],
        'focus': ['ambient', 'classical'],
        'party': ['dance', 'hip-hop'],
        'workout': ['electronic', 'hip-hop']
    }

    return mood_genres.get(mood.lower(), ['pop', 'rock'])


def get_fallback_recommendations(top_artists, mood):
    """Fallback recommendations when API fails"""
    fallback_tracks = [
        {'title': 'Shape of You', 'artist': 'Ed Sheeran',
         'spotify_url': 'https://open.spotify.com/track/7qiZfU4dY1lWllzX7mPBI3'},
        {'title': 'Blinding Lights', 'artist': 'The Weeknd',
         'spotify_url': 'https://open.spotify.com/track/0VjIjW4GlULA3EkoBOIsMf'},
        {'title': 'Good 4 U', 'artist': 'Olivia Rodrigo',
         'spotify_url': 'https://open.spotify.com/track/4ZtFanR9U6ndgddUvNcjcG'},
        {'title': 'Levitating', 'artist': 'Dua Lipa',
         'spotify_url': 'https://open.spotify.com/track/463CkQjx2Zk1yXoBuierM9'},
        {'title': 'Stay', 'artist': 'The Kid LAROI & Justin Bieber',
         'spotify_url': 'https://open.spotify.com/track/5PjdY0CKGZdEuoNab3yDmX'}
    ]

    recommendations = []
    for track in fallback_tracks:
        recommendations.append({
            'title': track['title'],
            'artist': track['artist'],
            'match_score': 70 + random.randint(-5, 15),
            'spotify_url': track['spotify_url'],
            'reason': f"Popular recommendation" + (f" for {mood} mood" if mood else "")
        })

    return recommendations






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
