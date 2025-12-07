import os
import aiohttp
from asyncio import gather, run
from datetime import datetime, timezone

class MusicClient:
    """A concise, Pythonic client for Last.fm and ListenBrainz."""

    def __init__(self, api_key=None, storage_adapter=None):
        self.api_key = api_key
        self.R = storage_adapter
        self.session = aiohttp.ClientSession()
        self._playcount_getters = {
            "lastfm": self._get_lastfm_playcount,
            "listenbrainz": self._get_listenbrainz_playcount,
        }

    async def close(self):
        await self.session.close()

    def _format_time_ago(self, timestamp):
        if not timestamp:
            return None
        diff = (datetime.now(timezone.utc) - datetime.fromtimestamp(timestamp, timezone.utc)).total_seconds()
        hours, minutes = int(diff // 3600), int((diff % 3600) // 60)
        return f"{hours}h ago" if hours else f"{minutes}m ago" if minutes else "just now"

    def format_song(self, service, username, nick, song):
        if not song:
            return None

        status = "now playing" if song["is_playing"] else self._format_time_ago(song["timestamp"])
        album_part = f"from {song['album']}" if song['album'] else ""
        playcount_part = f"[{song['playcount']} plays]" if song.get('playcount', 0) > 0 else ""

        user_part = f"{service}:{username}({nick})" if nick else f"{service}:{username}"
        track_part = f"{status}: {song['artist']} - {song['name']}"

        return " ".join(filter(None, [user_part, track_part, album_part, playcount_part]))

    # --- Service-Specific Helpers ---

    def _parse_lastfm_response(self, response):
        try:
            track = response["recenttracks"]["track"][0]
            is_playing = "@attr" in track and "nowplaying" in track["@attr"]
            return {
                "artist": track["artist"]["#text"], "album": track["album"]["#text"] or None,
                "name": track["name"], "is_playing": is_playing,
                "timestamp": None if is_playing else int(track.get("date", {}).get("uts", 0)),
                "playcount": 0
            }
        except (KeyError, IndexError, TypeError):
            return None

    def _parse_listenbrainz_response(self, response):
        try:
            listen = response["payload"]["listens"][0]
            meta = listen["track_metadata"]
            is_playing = listen.get("playing_now", False)
            return {
                "artist": meta["artist_name"], "album": meta.get("release_name"),
                "name": meta["track_name"], "is_playing": is_playing,
                "timestamp": None if is_playing else listen.get("listened_at"),
                "playcount": 0
            }
        except (KeyError, IndexError, TypeError):
            return None

    async def _get_lastfm_playcount(self, artist, track, username):
        if not self.api_key: return 0
        url = "https://ws.audioscrobbler.com/2.0/"
        params = {"method": "track.getInfo", "format": "json", "artist": artist, "track": track, "username": username, "api_key": self.api_key}
        try:
            async with self.session.get(url, params=params) as resp:
                return int((await resp.json())["track"]["userplaycount"])
        except (KeyError, ValueError, aiohttp.ClientError):
            return 0

    async def _get_listenbrainz_playcount(self, artist, track, username):
        url = f"https://api.listenbrainz.org/1/stats/user/{username}/recording"
        params = {"artist_name": artist, "track_name": track}
        try:
            async with self.session.get(url, params=params) as resp:
                return (await resp.json()).get("payload", {}).get("count", 0)
        except (aiohttp.ClientError, ValueError, KeyError):
            return 0

    # --- Core Logic ---

    async def _fetch_track(self, service, username):
        if service == "lastfm":
            url, params = "https://ws.audioscrobbler.com/2.0/", {"method": "user.getrecenttracks", "format": "json", "limit": 1, "user": username, "api_key": self.api_key}
            parser = self._parse_lastfm_response
        elif service == "listenbrainz":
            url, params = f"https://api.listenbrainz.org/1/user/{username}/listens", {"count": 1}
            parser = self._parse_listenbrainz_response
        else:
            return None

        try:
            async with self.session.get(url, params=params) as resp:
                return parser(await resp.json())
        except (aiohttp.ClientError, ValueError):
            return None

    async def get_now_playing(self, service, username=None, user_id=None, nick=None):
        username = username or await self.R.read(f"{service}:{user_id}")
        if not username: return None

        song = await self._fetch_track(service.lower(), username)
        if not song: return None

        get_playcount = self._playcount_getters.get(service.lower())
        if get_playcount:
            song["playcount"] = await get_playcount(song["artist"], song["name"], username)

        return {"song": song, "formatted": self.format_song(service, username, nick, song)}

    async def now_playing_for_users(self, users):
        tasks = (self.get_now_playing(u["service"], user_id=u["id"], nick=u.get("nick")) for u in users)
        return [d["formatted"] for d in await gather(*tasks) if d and d.get("formatted")]


class MockStorageAdapter:
    def __init__(self): self.data = {}
    async def read(self, key): return self.data.get(key)
    async def write(self, key, value): self.data[key] = value


async def main():
    lastfm_api_key = os.getenv("AIKTA_LASTFM_API_KEY")
    if not lastfm_api_key:
        print("Warning: AIKTA_LASTFM_API_KEY not set. Last.fm lookups will fail.")

    storage = MockStorageAdapter()
    test_users = [
        {"id": "user1", "service": "lastfm", "nick": "katia", "service_username": "unresolver"},
        {"id": "user2", "service": "listenbrainz", "nick": "katia", "service_username": "catia"}
    ]

    for user in test_users:
        await storage.write(f"{user['service']}:{user['id']}", user['service_username'])

    client = MusicClient(api_key=lastfm_api_key, storage_adapter=storage)

    print("Fetching now playing tracks...")
    results = await client.now_playing_for_users(test_users)

    print("\nResults:")
    print("\n".join(f"- {r}" for r in results) or "No tracks found for the test users.")

    await client.close()
    print("\nTest completed!")


if __name__ == "__main__":
    run(main())
