import { Client as PgClient } from "pg";

export async function withDb<T>(fn: (db: PgClient) => Promise<T>): Promise<T> {
  const db = new PgClient({ connectionString: process.env.DATABASE_URL });
  await db.connect();
  try {
    return await fn(db);
  } finally {
    await db.end();
  }
}

export async function countEvents(eventType: string, scenarioSessionId: string): Promise<number> {
  return withDb(async (db) => {
    const result = await db.query<{ count: number }>(
      "SELECT count(*)::int AS count FROM platform.event_log WHERE event_type = $1 AND scenario_session_id = $2",
      [eventType, scenarioSessionId],
    );
    return result.rows[0].count;
  });
}

