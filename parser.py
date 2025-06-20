def parse_search_query(query):
    """Parse search query to extract song, artist, year, and platform"""
    params = {}

    # Extract quoted values
    import re

    # Match song:"value"
    song_match = re.search(r'song:"([^"]+)"', query, re.IGNORECASE)
    if song_match:
        params['song'] = song_match.group(1)

    # Match artist:"value"
    artist_match = re.search(r'artist:"([^"]+)"', query, re.IGNORECASE)
    if artist_match:
        params['artist'] = artist_match.group(1)

    # Match year:value
    year_match = re.search(r'year:(\d{4})', query, re.IGNORECASE)
    if year_match:
        params['year'] = year_match.group(1)

    # Match platform:"value" or platform:value
    platform_match = re.search(r'platform:(?:"([^"]+)"|(\w+))', query, re.IGNORECASE)
    if platform_match:
        platform = platform_match.group(1) or platform_match.group(2)
        # Normalize platform names
        platform_lower = platform.lower()
        if platform_lower in ['spotify', 'spot']:
            params['platform'] = 'spotify'
        elif platform_lower in ['youtube', 'yt']:
            params['platform'] = 'youtube'
        elif platform_lower in ['yandex', 'yandex music', 'ym']:
            params['platform'] = 'yandex'
        else:
            params['platform'] = platform_lower

    return params