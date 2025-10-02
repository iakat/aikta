import json
import aiohttp
from asyncio import gather
from datetime import datetime, timezone

class LastFM:
    """Last.fm Now Playing Client with playcount and listening status."""

    def __init__(self, api_key, storage_adapter):
        self.api_key = api_key
        self.R = storage_adapter
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    def _parse_track(self, response):
        """Parse Last.fm response into a clean song dict."""
        try:
            track = response["recenttracks"]["track"][0]
            is_playing = "@attr" in track and "nowplaying" in track["@attr"]

            timestamp = None
            if not is_playing and "date" in track:
                timestamp = int(track["date"]["uts"])

            return {
                "artist": track["artist"]["#text"],
                "album": track["album"]["#text"] or None,
                "name": track["name"],
                "is_playing": is_playing,
                "timestamp": timestamp
            }
        except (KeyError, IndexError, ValueError):
            return None

    async def _get_playcount(self, artist, track, username):
        """Get user's playcount for a specific track."""
        url = "https://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "format": "json",
            "artist": artist,
            "track": track,
            "username": username,
            "api_key": self.api_key
        }

        try:
            async with self.session.get(url, params=params) as response:
                data = json.loads(await response.read())
                return int(data["track"]["userplaycount"])
        except (KeyError, ValueError, aiohttp.ClientError):
            return 0

    def _format_time_ago(self, timestamp):
        """Convert Unix timestamp to 'X hrs/min ago' format."""
        if not timestamp:
            return None

        now = datetime.now(timezone.utc)
        then = datetime.fromtimestamp(timestamp, timezone.utc)
        diff = (now - then).total_seconds()

        hours = int(diff // 3600)
        minutes = int((diff % 3600) // 60)

        if hours > 0:
            return f"{hours}h ago"
        elif minutes > 0:
            return f"{minutes}m ago"
        else:
            return "just now"

    def format_song(self, lfm, nick, song):
        """Format song info with playcount and status."""
        if not song:
            return None

        nick_part = f"({nick})" if nick else ""
        status = "now playing" if song["is_playing"] else self._format_time_ago(song["timestamp"])
        album_part = f"from {song['album']}" if song["album"] else ""
        playcount_part = f"[{song['playcount']} plays]" if song.get('playcount', 0) > 0 else ""

        parts = [
            f"{lfm}{nick_part}",
            f"{status}: {song['artist']} - {song['name']}",
            album_part,
            playcount_part
        ]

        return " ".join(filter(None, parts))

    async def get_now_playing(self, lfm=None, user_id=None, nick=None):
        """Get current/recent track for a user."""
        if not lfm and user_id:
            lfm = await self.R.read(f"lastfm:{user_id}")

        if not lfm:
            return None

        url = "https://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "user.getrecenttracks",
            "format": "json",
            "limit": 1,
            "user": lfm,
            "api_key": self.api_key
        }

        async with self.session.get(url, params=params) as response:
            data = json.loads(await response.read())

        song = self._parse_track(data)
        if not song:
            return None

        # Fetch playcount separately
        song["playcount"] = await self._get_playcount(song["artist"], song["name"], lfm)

        return {
            "song": song,
            "formatted": self.format_song(lfm, nick, song)
        }

    async def now_playing_for_users(self, users):
        """Get formatted tracks for multiple users (playing or recent)."""
        tasks = [
            self.get_now_playing(user_id=user["id"], nick=user.get("display_name"))
            for user in users
        ]

        results = []
        for data in await gather(*tasks):
            if data and data["formatted"]:
                results.append(data["formatted"])

        return results
