import aiohttp
import urllib.parse

async def search_apple_music(query):
    """Search for a song on Apple Music using iTunes API"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={encoded_query}&media=music&entity=song&limit=1"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    if data.get('results'):
                        return data['results'][0]
        except Exception as e:
            print(f"Error searching Apple Music: {e}")

    return None