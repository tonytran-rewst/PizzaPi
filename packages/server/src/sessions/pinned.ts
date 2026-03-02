import { kysely } from "../auth.js";

/**
 * Ensure the pinned sessions table exists.
 */
export async function ensurePinnedSessionTable(): Promise<void> {
    await kysely.schema
        .createTable("user_pinned_session")
        .ifNotExists()
        .addColumn("userId", "text", (col) => col.notNull())
        .addColumn("sessionId", "text", (col) => col.notNull())
        .addColumn("pinnedAt", "text", (col) => col.notNull())
        .execute();

    // Create a unique index on (userId, sessionId) to act as composite primary key
    await kysely.schema
        .createIndex("user_pinned_session_pk")
        .ifNotExists()
        .on("user_pinned_session")
        .columns(["userId", "sessionId"])
        .unique()
        .execute();
}

/**
 * Pin a session for a user.
 */
export async function pinSession(userId: string, sessionId: string): Promise<void> {
    const nowIso = new Date().toISOString();
    await kysely
        .insertInto("user_pinned_session")
        .values({ userId, sessionId, pinnedAt: nowIso })
        .onConflict((oc) => oc.columns(["userId", "sessionId"]).doNothing())
        .execute();
}

/**
 * Unpin a session for a user.
 */
export async function unpinSession(userId: string, sessionId: string): Promise<void> {
    await kysely
        .deleteFrom("user_pinned_session")
        .where("userId", "=", userId)
        .where("sessionId", "=", sessionId)
        .execute();
}

/**
 * Get all pinned session IDs for a user.
 */
export async function getPinnedSessionIds(userId: string): Promise<string[]> {
    const rows = await kysely
        .selectFrom("user_pinned_session")
        .select("sessionId")
        .where("userId", "=", userId)
        .orderBy("pinnedAt", "desc")
        .execute();
    return rows.map((r) => r.sessionId);
}

/**
 * Check if a specific session is pinned by a user.
 */
export async function isSessionPinned(userId: string, sessionId: string): Promise<boolean> {
    const row = await kysely
        .selectFrom("user_pinned_session")
        .select("sessionId")
        .where("userId", "=", userId)
        .where("sessionId", "=", sessionId)
        .executeTakeFirst();
    return !!row;
}
