import aiohttp
import base64
from settings import MusicRecognitionBot

bot_settings = MusicRecognitionBot()


# Get Token
async def get_spotify_token():
    """Get Spotify access token"""
    auth_string = f"{bot_settings.spotify_client_id}:{bot_settings.spotify_client_secret}"
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


## Search music from Spotify Music
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



## Analayze Music
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