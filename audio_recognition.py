import requests
import base64
import hashlib
import hmac
import time

from settings import MusicRecognitionBot

bot_settings = MusicRecognitionBot()
# ACRCloud integration for music recognition
def recognize_audio(audio_data):
    """Recognize audio using ACRCloud API"""
    timestamp = str(int(time.time()))
    string_to_sign = f"POST\n/v1/identify\n{bot_settings.acrcloud_access_key}\naudio\n1\n{timestamp}"
    signature = base64.b64encode(
        hmac.new(
            bot_settings.acrcloud_access_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
    ).decode('utf-8')

    files = {'sample': audio_data}
    data = {
        'access_key': bot_settings.acrcloud_access_key,
        'sample_bytes': len(audio_data),
        'timestamp': timestamp,
        'signature': signature,
        'data_type': 'audio',
        'signature_version': '1'
    }

    response = requests.post(f'http://{bot_settings.acrcloud_host}/v1/identify', files=files, data=data)
    return response.json()

