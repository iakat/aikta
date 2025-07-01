from os import environ, getenv
from pathlib import Path
LASTFM_API_KEY = environ["AIKTA_LASTFM_API_KEY"]
CHANNELS = environ["AIKTA_CHANNELS"].split(",")
NICK = getenv("AIKTA_NICK", "aikta")
SERVER = getenv("AIKTA_SERVER", "irc.hackint.org")
PORT = int(getenv("AIKTA_PORT", "6697"))
DATA_DIR = Path(getenv("AIKTA_DATA_DIR", "/data"))
