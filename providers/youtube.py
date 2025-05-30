import aiohttp
import urllib.parse
from typing import Optional, Dict, Any

from settings import MusicRecognitionBot

bot_settings = MusicRecognitionBot()


async def search_youtube_music(query: str) -> Optional[Dict[str, Any]]:
    """Search for a song on YouTube Music using YouTube Data API"""
    # YouTube Data API v3 - requires API key
    api_key = bot_settings.youtube_api_key  # Implement this function
    encoded_query = urllib.parse.quote(f"{query} music")

    url = (f"https://www.googleapis.com/youtube/v3/search"
           f"?part=snippet&type=video&q={encoded_query}"
           f"&videoCategoryId=10&maxResults=1&key={api_key}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('items'):
                        return data['items'][0]
        except Exception as e:
            print(f"Error searching YouTube: {e}")

    return None


async def search_youtube_unofficial(query: str) -> Optional[Dict[str, Any]]:
    """Search YouTube using unofficial method (web scraping approach)"""
    # This uses youtube-search-python library approach
    # Note: This is less reliable and may break with YouTube changes

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    # Parse HTML to extract video data
                    # This would require HTML parsing with BeautifulSoup or similar
                    # Implementation would be complex and fragile
                    return parse_youtube_html(html)  # You'd need to implement this
        except Exception as e:
            print(f"Error searching YouTube unofficially: {e}")

    return None


# Alternative: Using ytmusicapi for YouTube Music (more reliable)
async def search_youtube_music_ytapi(query: str) -> Optional[Dict[str, Any]]:
    """Search YouTube Music using ytmusicapi library"""
    # This requires: pip install ytmusicapi
    # Note: This is a synchronous library, so you'd need to wrap it

    from ytmusicapi import YTMusic
    import asyncio

    def sync_search():
        try:
            ytmusic = YTMusic()
            results = ytmusic.search(query, filter="songs", limit=1)
            return results[0] if results else None
        except Exception as e:
            print(f"Error with ytmusicapi: {e}")
            return None

    # Run in executor to avoid blocking
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sync_search)
    return result


