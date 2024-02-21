from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AceBot

async def get_all(bot: 'AceBot', id: int):
    async with bot.pool.acquire() as conn:
        return [x for x in await conn.fetchall("SELECT * FROM guildConfig WHERE id = :id;", {"id": id})]

async def get_value(bot: 'AceBot', id: int, key: str):
    async with bot.pool.acquire() as conn:
        return [x for x in await conn.fetchone("SELECT value FROM guildConfig WHERE id = :id AND key = :key;", {"id": id, "key": key})]

async def set_value(bot: 'AceBot', id: int, key: str, value:int):
    async with bot.pool.acquire() as conn:
        await conn.execute("INSERT INTO guildConfig (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = :value WHERE id = :id AND key = :key;", {"id": id, "key": key, "value": value})
        await conn.commit()

async def get_balance(bot: 'AceBot', user: int):
    async with bot.pool.acquire() as conn:
        return [x for x in await conn.fetchone("SELECT money FROM users WHERE id = :user;", {"user": user})][0]
    
async def set_balance(bot: 'AceBot', user: int, money: int):
    async with bot.pool.acquire() as conn:
        await conn.execute("UPDATE users SET money = :money WHERE id = :user;", {"money": money, "user": user})
        await conn.commit()