import json
import aiohttp
from asyncio import gather

class LastFM:
    """
    Generic Last.fm Now Playing Client using a generic async key/value storage.
    User mapping is managed by Last.fm usernames only, without context.
    """

    def __init__(self, api_key, storage_adapter):
        """
        api_key: str - Your Last.fm API key.
        storage_adapter: object with async methods 'read(key)', 'write(key, value)'
        """
        self.api_key = api_key
        self.R = storage_adapter
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def _userid_to_lastfm(self, user_id, display_name=None):
        """
        Returns (lastfm_username, display_name) for a user id.
        """
        lfm = await self.R.read(f"lastfm:{user_id}")
        return lfm, display_name

    def _lastfm_response_to_song(self, response):
        print("debug: lastfm response", response)
        song = dict(is_playing=False)
        try:
            track = response["recenttracks"]["track"][0]
            song["artist"] = track["artist"]["#text"]
            song["album"] = track["album"]["#text"] or None
            song["name"] = track["name"]
            if "@attr" in track and "nowplaying" in track["@attr"]:
                song["is_playing"] = True
        except (KeyError, IndexError):
            song = dict(is_playing=True, artist=None, album=None, name=None)
        return song

    def format_song(self, lfm, nick, song):
        """
        Returns a formatted string for a song.
        """
        nick = f"({nick})" if nick else ""
        return " ".join(
            [
                f"{lfm}{nick}",
                f"now playing: {song['artist']} - {song['name']}",
                f"from {song['album']}" if song["album"] else "",
            ]
        )

    async def get_now_playing(self, lfm=None, user_id=None, nick=None):
        """
        Returns a dict with keys: "song" and "formatted"
        """
        if not lfm and user_id:
            lfm, nick = await self._userid_to_lastfm(user_id, nick)
        if not lfm:
            return None

        url = "https://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks"
        params = dict(
            format="json", limit=1, user=lfm, api_key=self.api_key
        )
        async with self.session.get(url, params=params) as response:
            response = json.loads(await response.read())
        song = self._lastfm_response_to_song(response)
        return {
            "song": song,
            "formatted": self.format_song(lfm, nick, song),
        }

    async def now_playing_for_users(self, users):
        """
        Returns a list of formatted now playing songs for a list of users.
        Each user is a dict with at least 'id' and optionally 'display_name'
        """
        tasks = [self.get_now_playing(user_id=user["id"], nick=user.get("display_name")) for user in users]
        results = []
        for data in await gather(*tasks):
            if data and data["song"]["is_playing"]:
                results.append(data["formatted"])
        return results
