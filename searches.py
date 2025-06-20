import aiohttp
import asyncio
import urllib.parse
from providers.spotify import get_spotify_token


from settings import MusicRecognitionBot

bot_settings = MusicRecognitionBot()


async def search_all_platforms(search_params):
    """Search across multiple music platforms or specific platform"""
    results = []

    # Check if user specified a platform
    target_platform = search_params.get('platform')

    # Create search tasks based on platform filter
    tasks = []

    if not target_platform or target_platform == 'spotify':
        tasks.append(('spotify', search_spotify(search_params)))

    if not target_platform or target_platform == 'youtube':
        tasks.append(('youtube', search_youtube(search_params)))

    if not target_platform or target_platform == 'yandex':
        tasks.append(('yandex', search_yandex_music(search_params)))

    # Execute searches concurrently
    platform_results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)

    # Combine results with platform info
    for i, platform_result in enumerate(platform_results):
        if isinstance(platform_result, list):
            platform_name = tasks[i][0]
            for result in platform_result:
                result['source_platform'] = platform_name
            results.extend(platform_result)

    # Remove duplicates and sort by relevance
    unique_results = []
    seen = set()

    for result in results:
        # Create a unique key based on title and artist
        key = f"{result['title'].lower()}-{result['artist'].lower()}"
        if key not in seen:
            seen.add(key)
            unique_results.append(result)

    return unique_results


async def search_spotify(search_params):
    """Search Spotify API with real API calls"""
    try:
        # First, get access token
        access_token = await get_spotify_token()
        if not access_token:
            return []

        # Build search query
        query_parts = []
        if search_params.get('song'):
            query_parts.append(search_params['song'])
        if search_params.get('artist'):
            query_parts.append(search_params['artist'])

        search_query = " ".join(query_parts)

        # Make actual API call
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            params = {
                'q': search_query,
                'type': 'track',
                'limit': 10
            }

            # Add year filter if specified
            if search_params.get('year'):
                params['q'] += f" year:{search_params['year']}"

            url = 'https://api.spotify.com/v1/search'

            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []

                    for track in data.get('tracks', {}).get('items', []):
                        # Filter by artist if specified
                        if search_params.get('artist'):
                            artist_names = [artist['name'].lower() for artist in track['artists']]
                            if not any(search_params['artist'].lower() in name for name in artist_names):
                                continue

                        # Convert duration from ms to mm:ss
                        duration_ms = track.get('duration_ms', 0)
                        duration_min = duration_ms // 60000
                        duration_sec = (duration_ms % 60000) // 1000
                        duration_str = f"{duration_min}:{duration_sec:02d}"

                        # Extract year from release date
                        release_date = track.get('album', {}).get('release_date', '')
                        year = release_date.split('-')[0] if release_date else 'Unknown'

                        results.append({
                            'title': track['name'],
                            'artist': ', '.join([artist['name'] for artist in track['artists']]),
                            'album': track.get('album', {}).get('name', 'Unknown'),
                            'year': year,
                            'duration': duration_str,
                            'spotify_url': track.get('external_urls', {}).get('spotify', ''),
                            'preview_url': track.get('preview_url')
                        })

                    return results
                else:
                    print(f"Spotify API error: {response.status}")
                    return []

    except Exception as e:
        print(f"Spotify search error: {e}")
        return []


async def search_youtube(search_params):
    """Search YouTube API with real API calls"""
    try:
        YOUTUBE_API_KEY = bot_settings.youtube_api_key # Get from Google Cloud Console

        if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "your_youtube_api_key":
            print("YouTube API key not configured")
            return []

        # Build search query
        query_parts = []
        if search_params.get('song'):
            query_parts.append(search_params['song'])
        if search_params.get('artist'):
            query_parts.append(search_params['artist'])

        search_query = " ".join(query_parts)

        async with aiohttp.ClientSession() as session:
            params = {
                'part': 'snippet',
                'q': search_query,
                'type': 'video',
                'videoCategoryId': '10',  # Music category
                'maxResults': 10,
                'key': YOUTUBE_API_KEY
            }

            url = 'https://www.googleapis.com/youtube/v3/search'

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []

                    for item in data.get('items', []):
                        # Extract video details
                        video_id = item['id']['videoId']
                        title = item['snippet']['title']
                        channel = item['snippet']['channelTitle']

                        # Filter by artist if specified
                        if search_params.get('artist'):
                            if search_params['artist'].lower() not in title.lower() and \
                                    search_params['artist'].lower() not in channel.lower():
                                continue

                        # Get video duration (requires additional API call)
                        duration = await get_youtube_duration(video_id, YOUTUBE_API_KEY, session)

                        results.append({
                            'title': search_params.get('song', title.split('-')[0].strip() if '-' in title else title),
                            'artist': search_params.get('artist', channel),
                            'duration': duration,
                            'youtube_url': f"https://www.youtube.com/watch?v={video_id}",
                            'thumbnail': item['snippet']['thumbnails']['default']['url']
                        })

                    return results
                else:
                    print(f"YouTube API error: {response.status}")
                    return []

    except Exception as e:
        print(f"YouTube search error: {e}")
        return []


async def get_youtube_duration(video_id, api_key, session):
    """Get YouTube video duration"""
    try:
        params = {
            'part': 'contentDetails',
            'id': video_id,
            'key': api_key
        }

        url = 'https://www.googleapis.com/youtube/v3/videos'

        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('items'):
                    duration_str = data['items'][0]['contentDetails']['duration']
                    # Convert PT4M33S to 4:33
                    import re
                    match = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', duration_str)
                    if match:
                        minutes = int(match.group(1) or 0)
                        seconds = int(match.group(2) or 0)
                        return f"{minutes}:{seconds:02d}"

    except Exception as e:
        print(f"Duration fetch error: {e}")

    return "Unknown"


async def search_yandex_music(search_params):
    """Search Yandex Music"""
    try:
        # Build search query
        query_parts = []
        if search_params.get('song'):
            query_parts.append(search_params['song'])
        if search_params.get('artist'):
            query_parts.append(search_params['artist'])

        search_query = " ".join(query_parts)

        # Note: You'll need Yandex Music API access for actual implementation
        # This is a placeholder

        results = []
        if search_query:
            results.append({
                'title': search_params.get('song', 'Unknown'),
                'artist': search_params.get('artist', 'Unknown'),
                'duration': '3:45',
                'yandex_url': f"https://music.yandex.com/search?text={urllib.parse.quote(search_query)}"
            })

        return results

    except Exception as e:
        print(f"Yandex Music search error: {e}")
        return []