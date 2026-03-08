## ADDED Requirements

### Requirement: Test coverage for database layer
The system SHALL have `tests/unit/test_models.py` for SQLAlchemy model validation and `tests/integration/test_db.py` for Alembic migration and CRUD tests before `models.py`, `db.py`, or migrations are written.

## Test Requirements

The following test scenarios MUST be implemented before any database code is written.

#### Scenario: Alembic upgrade head creates conversations and messages tables
- **WHEN** `alembic upgrade head` is run programmatically against a fresh test PostgreSQL database (via the `db_session` fixture)
- **THEN** the test queries `information_schema.tables` and asserts both `conversations` and `messages` exist with the expected columns

#### Scenario: Alembic upgrade head is idempotent
- **WHEN** `alembic upgrade head` is called a second time against an already-migrated database
- **THEN** no exception is raised and no schema changes occur

#### Scenario: Conversation insert and user_id filter
- **WHEN** two conversations are inserted — one for `alice@example.com` and one for `bob@example.com` — and queried with `WHERE user_id = 'alice@example.com'`
- **THEN** only the conversation belonging to Alice is returned

#### Scenario: Messages cascade-delete with conversation
- **WHEN** a conversation row is deleted from `conversations`
- **THEN** all rows in `messages` with matching `conversation_id` are also deleted (verified by asserting `SELECT COUNT(*) FROM messages WHERE conversation_id = ...` returns `0`)

#### Scenario: updated_at refreshed when message is added
- **WHEN** a message is inserted for a conversation, triggering the update of `conversations.updated_at`
- **THEN** the conversation's `updated_at` timestamp is greater than its `created_at` timestamp

#### Scenario: Message role constraint rejects invalid values
- **WHEN** a `Message` row is inserted with `role="system"` (not in the allowed set `{user, assistant}`)
- **THEN** the database raises a constraint violation exception

#### Scenario: User isolation — GET conversations returns only caller's rows
- **WHEN** the conversations CRUD function is called with `user_id="alice@example.com"`
- **THEN** it returns only rows where `user_id = "alice@example.com"` even if the database contains rows for other users

#### Scenario: Message lookup for non-owned conversation returns empty
- **WHEN** `get_messages(conversation_id, user_id="bob@example.com")` is called for a conversation owned by Alice
- **THEN** the function returns an empty list or raises a 404-equivalent error (no ownership leak)
