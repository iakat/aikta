from ircrobots import Server, Bot
from aikta.sqlite import Storage
from aikta.settings import SERVER, PORT, NICK, LASTFM_API_KEY, CHANNELS
from aikta.lastfm import LastFM
import ircrobots.security
import asyncio

from irctokens import build, Line
from ircrobots import Bot as BaseBot, Server as BaseServer, ConnectionParams

class Server(BaseServer):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.storage = Storage("aikta.db")
        self.lastfm = LastFM(LASTFM_API_KEY, self.storage)
        self.channel_nicks = {}

    async def line_read(self, line: Line):
        print(f"{self.name} < {line.format()}")

        if line.command == "001":
            print(f"connected to {self.isupport.network}")
            for channel in CHANNELS:
                await self.send(build("JOIN", [channel]))

        elif line.command == "353":  # NAMES
            channel = line.params[2]
            names = [n.lstrip("@+%&~") for n in line.params[3].split()]
            self.channel_nicks[channel] = names

        elif line.command == "PRIVMSG":
            target, msg = line.params[:2]
            nick = line.source.split("!")[0]
            user_id = nick  # Using nick as user_id for storage

            if msg.startswith(".np"):
                _, *rest = msg.split()
                lfm_user = rest[0] if rest else await self.storage.read(f"lastfm:{user_id}")

                if rest:
                    await self.storage.write(f"lastfm:{user_id}", lfm_user)

                if not lfm_user:
                    await self.send(build("PRIVMSG", [target, f"{nick}: set your lastfm: .np unresolver"]))
                    return

                data = await self.lastfm.get_now_playing(lfm=lfm_user, nick=nick)
                resp = data["formatted"] if data and data["song"]["artist"] else f"{nick}: No recent track found."
                await self.send(build("PRIVMSG", [target, resp]))

            elif msg.startswith(".wp"):
                await self.send(build("NAMES", [target]))
                await asyncio.sleep(1.0)
                nicks = self.channel_nicks.get(target, [])
                users = [{"id": n, "display_name": n} for n in nicks]
                results = await self.lastfm.now_playing_for_users(users)
                if results:
                    for result in results:
                        await self.send(build("PRIVMSG", [target, result]))
                        await asyncio.sleep(1.0)
                else:
                    await self.send(build("PRIVMSG", [target, "..."]))

    async def line_send(self, line: Line):
        print(f"{self.name} > {line.format()}")

class Bot(BaseBot):
    def create_server(self, name: str):
        return Server(self, name)

async def main():
    bot = Bot()
    params = ConnectionParams(NICK, SERVER, PORT)
    print("connecting to ", params)
    await bot.add_server('default', params)
    await bot.run()

def cli_main():
    """Synchronous entry point for CLI script"""
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
