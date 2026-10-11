import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Inbound


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def init(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                  phone TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'active',
                  summary TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL,
                  last_incoming_at REAL NOT NULL DEFAULT 0,
                  last_error TEXT NOT NULL DEFAULT '', summary_source TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS messages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL,
                  wa_id TEXT UNIQUE, direction TEXT NOT NULL, type TEXT NOT NULL,
                  text TEXT NOT NULL DEFAULT '', media_id TEXT NOT NULL DEFAULT '',
                  timestamp REAL NOT NULL, received_at REAL NOT NULL,
                  state TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                  reply_to INTEGER UNIQUE, actor TEXT NOT NULL DEFAULT 'customer',
                  FOREIGN KEY(phone) REFERENCES conversations(phone)
                );
                CREATE INDEX IF NOT EXISTS idx_jobs ON messages(direction,state,id);
                CREATE INDEX IF NOT EXISTS idx_history ON messages(phone,id);
                CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
            """)

    def recover(self):
        # A process interruption may have happened after Meta accepted a send.
        # Never automatically replay an ambiguous send.
        with self.connect() as con:
            phones = con.execute("SELECT DISTINCT phone FROM messages WHERE state IN ('processing','sending')").fetchall()
            for row in phones:
                con.execute("UPDATE conversations SET status='human_required', last_error='restart_interrupted', summary='Server stopped during processing. Review delivery before resuming.', summary_source='fallback' WHERE phone=?", (row[0],))
                con.execute("UPDATE messages SET state='suppressed' WHERE phone=? AND direction='incoming' AND state='queued'", (row[0],))
            con.execute("UPDATE messages SET state='uncertain',error='restart_interrupted' WHERE state='sending'")
            con.execute("UPDATE messages SET state='failed',error='restart_interrupted' WHERE state='processing'")

    def receive(self, message: Inbound) -> bool:
        now = time.time()
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO conversations(phone,updated_at) VALUES (?,?)", (message.phone, now))
            status = con.execute("SELECT status FROM conversations WHERE phone=?", (message.phone,)).fetchone()[0]
            state = "suppressed" if status != "active" else "queued"
            cur = con.execute("""INSERT OR IGNORE INTO messages
              (phone,wa_id,direction,type,text,media_id,timestamp,received_at,state)
              VALUES (?,?,'incoming',?,?,?,?,?,?)""",
              (message.phone, message.id, message.type, message.text, message.media_id,
               min(message.timestamp, now), now, state))
            if cur.rowcount:
                con.execute("UPDATE conversations SET last_incoming_at=MAX(last_incoming_at,?), updated_at=? WHERE phone=?", (min(message.timestamp, now), now, message.phone))
            return bool(cur.rowcount)

    def next_job(self):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM messages WHERE direction='incoming' AND state='queued' ORDER BY id LIMIT 1").fetchone()
            if row:
                con.execute("UPDATE messages SET state='processing' WHERE id=?", (row["id"],))
                return dict(row)
        return None

    def finish(self, ident: int, state: str = "done", error: str = ""):
        with self.connect() as con:
            con.execute("UPDATE messages SET state=?,error=? WHERE id=?", (state, error, ident))

    def set_transcript(self, ident: int, text: str):
        with self.connect() as con:
            con.execute("UPDATE messages SET text=? WHERE id=?", (text, ident))

    def conversation(self, phone: str):
        with self.connect() as con:
            row = con.execute("SELECT * FROM conversations WHERE phone=?", (phone,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["wa_link"] = f"https://wa.me/{phone}"
        return result

    def list_conversations(self, status: str | None, limit: int, offset: int):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM conversations WHERE (? IS NULL OR status=?) ORDER BY updated_at DESC LIMIT ? OFFSET ?", (status, status, limit, offset)).fetchall()
        return [dict(r, wa_link=f'https://wa.me/{r["phone"]}') for r in rows]

    def history(self, phone: str, limit: int = 10, through: int | None = None):
        with self.connect() as con:
            rows = con.execute("""SELECT * FROM messages WHERE phone=? AND text!=''
              AND (direction='incoming' OR state IN ('accepted','sent','delivered','read'))
              AND (? IS NULL OR id<? OR (direction='outgoing' AND reply_to<?))
              ORDER BY id DESC LIMIT ?""", (phone, through, through, through, limit if through is None else limit-1)).fetchall()
            current = con.execute("SELECT * FROM messages WHERE id=? AND phone=?", (through, phone)).fetchone() if through is not None else None
        result = [dict(r) for r in reversed(rows)]
        # The response to an earlier queued message can have a newer DB ID than
        # this job. Keep it in memory, then put the current user turn last.
        if current and current["text"]:
            result.append(dict(current))
        return result

    def messages(self, phone: str, limit: int, before: int | None = None):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM messages WHERE phone=? AND (? IS NULL OR id<?) ORDER BY id DESC LIMIT ?", (phone, before, before, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def set_status(self, phone: str, status: str, summary: str | None = None,
                   source: str = "", error: str = ""):
        with self.connect() as con:
            con.execute("""UPDATE conversations SET status=?,summary=COALESCE(?,summary),
                summary_source=CASE WHEN ?='' THEN summary_source ELSE ? END,
                last_error=?,updated_at=? WHERE phone=?""", (status, summary, source, source, error, time.time(), phone))
            if status != "active":
                con.execute("UPDATE messages SET state='suppressed' WHERE phone=? AND state='queued' AND direction='incoming'", (phone,))

    def begin_send(self, phone: str, text: str, reply_to: int | None, actor: str):
        with self.connect() as con:
            cur = con.execute("""INSERT INTO messages
              (phone,direction,type,text,timestamp,received_at,state,reply_to,actor)
              VALUES (?,'outgoing','text',?,?,?,'sending',?,?)""",
              (phone, text, time.time(), time.time(), reply_to, actor))
            return cur.lastrowid

    def sent(self, ident: int, wa_id: str):
        with self.connect() as con:
            con.execute("UPDATE messages SET wa_id=?,state='accepted' WHERE id=?", (wa_id, ident))

    def delivery(self, wa_id: str, state: str, code: str):
        rank = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 4}
        with self.connect() as con:
            row = con.execute("SELECT phone,state FROM messages WHERE wa_id=? AND direction='outgoing'", (wa_id,)).fetchone()
            if row and state in rank and rank[state] >= rank.get(row["state"], -1):
                con.execute("UPDATE messages SET state=?,error=? WHERE wa_id=?", (state, code, wa_id))
                if state == "failed":
                    con.execute("UPDATE conversations SET status='human_required',last_error=?,summary='Meta reported message delivery failure. Check the message error code.',summary_source='fallback' WHERE phone=?", (code or "meta_delivery_failed", row["phone"]))
                    con.execute("UPDATE messages SET state='suppressed' WHERE phone=? AND state='queued'", (row["phone"],))

    def reserve_groq_call(self, limit: int) -> bool:
        day = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT OR IGNORE INTO usage VALUES (?,0)", (day,))
            cur = con.execute("UPDATE usage SET calls=calls+1 WHERE day=? AND calls<?", (day, limit))
            return bool(cur.rowcount)
