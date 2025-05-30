import os
import discord
from discord.ext import commands

from db import init_db

from dotenv import load_dotenv
load_dotenv()


class MusicRecognitionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='/', intents=intents)
        self.acrcloud_host = 'identify-ap-southeast-1.acrcloud.com'
        self.acrcloud_access_key = os.getenv('ACRCLOUD_ACCESS_KEY')
        self.acrcloud_access_secret = os.getenv('ACRCLOUD_ACCESS_SECRET')
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
        self.yandex_client_id = os.getenv('YANDEX_CLIENT_ID')
        self.yandex_client_secret = os.getenv('YANDEX_CLIENT_SECRET')

        init_db()

    async def on_ready(self):
        print(f'{self.user} is ready to recognize music!')
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="for music to identify"))

