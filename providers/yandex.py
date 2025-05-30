import aiohttp
import base64
from settings import MusicRecognitionBot
import urllib.parse
from typing import Optional, Dict, Any


bot_settings = MusicRecognitionBot()


## Get Token
async def get_yandex_token():
    """Get Yandex Music access token using OAuth2"""
    # Yandex OAuth endpoint
    url = "https://oauth.yandex.ru/token"

    # Basic auth with client credentials
    auth_string = f"{bot_settings.yandex_client_id}:{bot_settings.yandex_client_secret}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            json_result = await response.json()
            return json_result["access_token"]



## Search music from Yandex Music
async def search_yandex_music(query: str) -> Optional[Dict[str, Any]]:
    """Search for a song on Yandex Music"""
    # Note: Yandex Music API requires authentication and is not publicly available
    # This is a conceptual implementation - you'd need proper API access

    encoded_query = urllib.parse.quote(query)
    url = f"https://api.music.yandex.net/search?text={encoded_query}&type=track&page=0&playlist-in-best=true"

    # You would need to get Yandex Music API token
    token = await get_yandex_token()  # Implement this function
    headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('result') and data['result'].get('tracks'):
                        tracks = data['result']['tracks']['results']
                        if tracks:
                            return tracks[0]  # Return first track
        except Exception as e:
            print(f"Error searching Yandex Music: {e}")

    return None
