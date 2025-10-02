from ircrobots import Bot as BaseBot, Server as BaseServer, ConnectionParams
from irctokens import build, Line
from aikta.sqlite import Storage
from aikta.settings import SERVER, PORT, NICK, LASTFM_API_KEY, CHANNELS, DATA_DIR
from aikta.lastfm import LastFM
import asyncio
from pathlib import Path


class Server(BaseServer):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.storage = Storage(db=Path(DATA_DIR) / "aikta.db")
        self.lastfm = LastFM(LASTFM_API_KEY, self.storage)

    async def line_read(self, line: Line):
        print(f"{self.name} < {line.format()}")

        match line.command:
            case "001":
                print(f"connected to {self.isupport.network}")
                for channel in CHANNELS:
                    await self.send(build("JOIN", [channel]))

            case "PRIVMSG":
                target, msg = line.params[:2]
                nick = line.source.split("!")[0]

                match msg.split()[0]:
                    case ".np": await self._handle_np(target, nick, msg)
                    case ".wp": await self._handle_wp(target)
                    case ".v": await self._handle_version(target)

    async def _handle_np(self, target, nick, msg):
        args = msg.split()[1:]
        lfm_user = args[0] if args else await self.storage.read(f"lastfm:{nick}")

        if args:
            await self.storage.write(f"lastfm:{nick}", lfm_user)

        if not lfm_user:
            return await self.send(build("PRIVMSG", [target, f"{nick}: set your lastfm: .np username"]))

        data = await self.lastfm.get_now_playing(lfm=lfm_user, nick=nick)
        resp = data["formatted"] if data and data["song"]["artist"] else f"{nick}: No recent track found."
        await self.send(build("PRIVMSG", [target, resp]))

    async def _handle_wp(self, target):
        if not (channel := self.channels.get(target)):
            return

        users = [{"id": n, "display_name": n} for n in channel.users]
        results = await self.lastfm.now_playing_for_users(users)

        for result in results or ["..."]:
            await self.send(build("PRIVMSG", [target, result]))
            await asyncio.sleep(1.0)

    async def _handle_version(self, target):
        version_file = Path("/app/.venv/.git_commit")
        version = version_file.read_text().strip() if version_file.exists() else "idk (file not found)"
        await self.send(build("PRIVMSG", [target, version]))

    async def line_send(self, line: Line):
        print(f"{self.name} > {line.format()}")


class Bot(BaseBot):
    def create_server(self, name: str) -> Server:
        return Server(self, name)


async def _main():
    bot = Bot()
    await bot.add_server('default', ConnectionParams(NICK, SERVER, PORT))
    await bot.run()

def main():
    """Synchronous entry point for CLI script"""
    asyncio.run(_main())

if __name__ == "__main__":
    main()
