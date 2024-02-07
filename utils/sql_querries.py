import sqlite3

def get_all(con: sqlite3.Connection, id: int):
    return con.cursor().execute("SELECT * FROM guildConfig WHERE id = :id;", {"id": id}).fetchall()

def get_value(con: sqlite3.Connection, id: int, key: str):
    return con.cursor().execute("SELECT value FROM guildConfig WHERE id = :id AND key = :key;", {"id": id, "key": key}).fetchall()

def set_value(con: sqlite3.Connection, id: int, key: str, value:int):
    con.cursor().execute("INSERT INTO guildConfig (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = :value WHERE id = :id AND key = :key;", {"id": id, "key": key, "value": value})
    con.commit()

def get_balance(con: sqlite3.Connection, user: int):
    return con.cursor().execute("SELECT money FROM users WHERE id = :user;", {"user": user}).fetchone()[0]

def set_balance(con: sqlite3.Connection, user: int, money: int):
    con.cursor().execute("UPDATE users SET money = :money WHERE id = :user;", {"money": money, "user": user})
    con.commit()