import aiosqlite


class Storage:
    def __init__(self, db="store.db"): self.db, self.i = db, 0
    async def _i(self):
        if self.i:
            return
        async with aiosqlite.connect(self.db) as d:
            await d.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
            await d.commit()
        self.i = 1
    async def read(self, k):
        await self._i()
        async with aiosqlite.connect(self.db) as d:
            a = await d.execute("SELECT v FROM kv WHERE k=?", (k,))
            r = await a.fetchone()
            return r[0] if r else None
    async def write(self, k, v):
        await self._i()
        async with aiosqlite.connect(self.db) as d:
            await d.execute("INSERT OR REPLACE INTO kv (k,v) VALUES (?,?)", (k,v))
            await d.commit()
    async def delete(self, k):
        await self._i()
        async with aiosqlite.connect(self.db) as d:
            await d.execute("DELETE FROM kv WHERE k=?", (k,))
            await d.commit()
    async def keys(self, p=None):
        await self._i()
        async with aiosqlite.connect(self.db) as d:
            q = "SELECT k FROM kv" + (" WHERE k LIKE ?" if p else "")
            c = (f"{p}%",) if p else ()
            a = await d.execute(q, c)
            return [r[0] async for r in a]
