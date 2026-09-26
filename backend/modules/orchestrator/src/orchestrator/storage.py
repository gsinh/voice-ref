"""Conversation state lives in Postgres (LangGraph checkpointer), in the orchestrator's
own schema. Tables are created by the `migrate` admin command, not at request time."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def setup_storage(database_url: str) -> None:
    async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
        await saver.setup()
