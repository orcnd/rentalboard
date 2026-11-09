"""A single query boundary for local SQLite and Cloudflare D1."""
import json


class SQLiteStore:
    def __init__(self, path):
        self.path = str(path)

    def connect(self):
        import sqlite3
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    async def query(self, sql, params=()):
        db = self.connect()
        try:
            with db:
                cursor = db.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()] if cursor.description else []
        finally:
            db.close()

    async def batch(self, statements):
        db = self.connect()
        try:
            with db:
                for sql, params in statements:
                    db.execute(sql, params)
        finally:
            db.close()


class D1Store:
    def __init__(self, binding):
        self.binding = binding

    async def query(self, sql, params=()):
        result = await self.binding.prepare(sql).bind(*params).all()
        rows = result.results
        if hasattr(rows, 'to_py'):
            rows = rows.to_py()
        return [dict(row) for row in rows]

    async def batch(self, statements):
        prepared = [self.binding.prepare(sql).bind(*params) for sql, params in statements]
        await self.binding.batch(prepared)
