## ADDED Requirements

### Requirement: Conversations table schema
The system SHALL maintain a `conversations` table in Lakebase (PostgreSQL via SQLAlchemy) with columns: `id` (UUID primary key), `user_id` (text, not null), `title` (text, nullable), `created_at` (timestamptz), `updated_at` (timestamptz auto-updated on modification).

#### Scenario: Conversation record created on POST
- **WHEN** `POST /api/conversations` succeeds
- **THEN** a row is inserted into `conversations` with the resolved `user_id`, a generated UUID `id`, and `created_at`/`updated_at` set to current timestamp

#### Scenario: updated_at refreshed on new message
- **WHEN** a message is persisted to the `messages` table for a conversation
- **THEN** the parent conversation's `updated_at` is updated to the current timestamp

### Requirement: Messages table schema
The system SHALL maintain a `messages` table in Lakebase with columns: `id` (UUID primary key), `conversation_id` (UUID foreign key → conversations.id, cascade delete), `user_id` (text, not null), `role` (text, constrained to `user` or `assistant`), `content` (text, not null), `created_at` (timestamptz).

#### Scenario: Messages stored after successful turn
- **WHEN** a streaming turn completes
- **THEN** two rows are inserted into `messages`: one with `role=user` containing the user's input, and one with `role=assistant` containing the full concatenated response text

#### Scenario: Messages cascade-deleted with conversation
- **WHEN** a conversation row is deleted
- **THEN** all `messages` rows with matching `conversation_id` are automatically deleted via the foreign key cascade

### Requirement: User isolation enforced at query layer
The system SHALL filter all conversation and message queries by the `user_id` resolved from the request token, ensuring users cannot read or modify other users' data.

#### Scenario: List returns only caller's conversations
- **WHEN** user A and user B each have conversations
- **THEN** `GET /api/conversations` for user A returns only user A's conversations

#### Scenario: Message lookup blocked for non-owner
- **WHEN** user B requests messages for a `conversation_id` owned by user A
- **THEN** the system returns `404 Not Found` (same as not found — no ownership leak)

### Requirement: Schema migration via Alembic
The system SHALL use Alembic to manage `conversations` and `messages` table migrations, with an initial migration that creates both tables from scratch and a `env.py` wired to the app's SQLAlchemy engine.

#### Scenario: Fresh database migration
- **WHEN** `alembic upgrade head` is run against an empty Lakebase database
- **THEN** `conversations` and `messages` tables are created with all columns, constraints, and indexes

#### Scenario: Idempotent migration
- **WHEN** `alembic upgrade head` is run a second time against an already-migrated database
- **THEN** no errors occur and no schema changes are made

### Requirement: Schema initialized at app startup
The system SHALL run `alembic upgrade head` (or equivalent programmatic migration) during the FastAPI lifespan `startup` event so the database is always schema-current before requests are served.

#### Scenario: App starts with valid schema
- **WHEN** the FastAPI app starts and the Lakebase connection is healthy
- **THEN** the startup event completes migration without error and the app begins accepting requests

## Test Requirements

Tests MUST be written in `tests/unit/test_models.py` (model validation) and `tests/integration/test_db.py` (Alembic + CRUD) BEFORE any database code is written (RED phase). Integration tests use the `db_session` fixture which connects to a test PostgreSQL instance.

Required test scenarios:
- `alembic upgrade head` on a fresh database creates `conversations` and `messages` tables with all columns
- `alembic upgrade head` called a second time raises no exceptions and makes no changes
- Inserting a conversation for Alice, then querying with `user_id=alice@example.com` returns only Alice's row
- Deleting a conversation cascades to delete all its messages
- Inserting a message updates the parent conversation's `updated_at` to be newer than `created_at`
- Inserting a message with `role="system"` raises a database constraint violation
- `get_conversations(user_id="alice")` with mixed-user data returns only Alice's conversations
- `get_messages(conversation_id, user_id="bob")` for Alice's conversation returns empty / raises 404
