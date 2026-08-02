"""
Fix chat_messages table — check and create if missing.
Run: python fix_chat_table.py
"""

import asyncio
import asyncpg


async def fix():
    conn = await asyncpg.connect(
        host="localhost", port=5432,
        user="postgres", password="123456",
        database="nutriagent",
    )
    print("Connected to PostgreSQL")

    # Check chat_sessions
    sessions_exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='chat_sessions')"
    )
    print(f"chat_sessions exists: {sessions_exists}")

    # Check chat_messages
    messages_exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='chat_messages')"
    )
    print(f"chat_messages exists: {messages_exists}")

    if not messages_exists:
        print("\nCreating chat_messages table...")
        await conn.execute("""
            CREATE TABLE chat_messages (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id      UUID         NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role            VARCHAR(16)  NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content         TEXT         NOT NULL,
                metadata_json   JSONB        DEFAULT '{}',
                embedding       VECTOR(1536),
                created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
            )
        """)
        print("chat_messages created!")

        # Create index
        await conn.execute(
            "CREATE INDEX idx_chat_messages_session "
            "ON chat_messages(session_id, created_at)"
        )
        print("Index created!")

    # Also recreate chat_sessions if missing
    if not sessions_exists:
        print("\nCreating chat_sessions table...")
        await conn.execute("""
            CREATE TABLE chat_sessions (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id         UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_type    VARCHAR(32)  DEFAULT 'chat',
                title           VARCHAR(256),
                is_active       BOOLEAN      DEFAULT TRUE,
                context_json    JSONB        DEFAULT '{}',
                created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
            )
        """)
        print("chat_sessions created!")

    # Verify by inserting a test row
    print("\nTest insert...")
    # Use an existing session or create one
    session_id = await conn.fetchval("SELECT id FROM chat_sessions LIMIT 1")
    if not session_id:
        session_id = await conn.fetchval(
            "INSERT INTO chat_sessions (user_id, session_type) "
            "SELECT id, 'chat' FROM users LIMIT 1 "
            "RETURNING id"
        )
        print(f"  Created test session: {session_id}")

    row = await conn.fetchrow(
        "INSERT INTO chat_messages (session_id, role, content) "
        "VALUES ($1, 'user', 'test message') RETURNING id, created_at",
        session_id,
    )
    print(f"  Message inserted: {row['id']} at {row['created_at']}")

    # Clean up test
    await conn.execute("DELETE FROM chat_messages WHERE content = 'test message'")
    print("  Test message cleaned up")

    await conn.close()
    print("\nDone! Chat tables are ready.")


asyncio.run(fix())
