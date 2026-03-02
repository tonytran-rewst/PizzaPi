import { describe, test, expect, beforeAll } from "bun:test";
import { Kysely, sql } from "kysely";
import { BunSqliteDialect } from "kysely-bun-sqlite";
import { Database } from "bun:sqlite";

// We'll test the pure SQL logic with an in-memory SQLite database.
// This avoids depending on the real auth.db and mirrors what pinned.ts does.

describe("pinned sessions store", () => {
    let db: Kysely<any>;

    beforeAll(async () => {
        const sqliteDb = new Database(":memory:");
        const dialect = new BunSqliteDialect({ database: sqliteDb });
        db = new Kysely<any>({ dialect });

        // Create the table (mirrors ensurePinnedSessionTable)
        await db.schema
            .createTable("user_pinned_session")
            .ifNotExists()
            .addColumn("userId", "text", (col) => col.notNull())
            .addColumn("sessionId", "text", (col) => col.notNull())
            .addColumn("pinnedAt", "text", (col) => col.notNull())
            .execute();

        await db.schema
            .createIndex("user_pinned_session_pk")
            .ifNotExists()
            .on("user_pinned_session")
            .columns(["userId", "sessionId"])
            .unique()
            .execute();
    });

    test("pin a session", async () => {
        await db
            .insertInto("user_pinned_session")
            .values({ userId: "user1", sessionId: "sess1", pinnedAt: new Date().toISOString() })
            .onConflict((oc) => oc.columns(["userId", "sessionId"]).doNothing())
            .execute();

        const rows = await db
            .selectFrom("user_pinned_session")
            .select("sessionId")
            .where("userId", "=", "user1")
            .execute();

        expect(rows).toHaveLength(1);
        expect(rows[0].sessionId).toBe("sess1");
    });

    test("pinning the same session twice is idempotent", async () => {
        await db
            .insertInto("user_pinned_session")
            .values({ userId: "user1", sessionId: "sess1", pinnedAt: new Date().toISOString() })
            .onConflict((oc) => oc.columns(["userId", "sessionId"]).doNothing())
            .execute();

        const rows = await db
            .selectFrom("user_pinned_session")
            .select("sessionId")
            .where("userId", "=", "user1")
            .execute();

        expect(rows).toHaveLength(1);
    });

    test("unpin a session", async () => {
        await db
            .deleteFrom("user_pinned_session")
            .where("userId", "=", "user1")
            .where("sessionId", "=", "sess1")
            .execute();

        const rows = await db
            .selectFrom("user_pinned_session")
            .select("sessionId")
            .where("userId", "=", "user1")
            .execute();

        expect(rows).toHaveLength(0);
    });

    test("pin multiple sessions and list them ordered by pinnedAt desc", async () => {
        await db
            .insertInto("user_pinned_session")
            .values({ userId: "user2", sessionId: "sessA", pinnedAt: "2025-01-01T00:00:00Z" })
            .execute();
        await db
            .insertInto("user_pinned_session")
            .values({ userId: "user2", sessionId: "sessB", pinnedAt: "2025-01-02T00:00:00Z" })
            .execute();
        await db
            .insertInto("user_pinned_session")
            .values({ userId: "user2", sessionId: "sessC", pinnedAt: "2025-01-03T00:00:00Z" })
            .execute();

        const rows = await db
            .selectFrom("user_pinned_session")
            .select("sessionId")
            .where("userId", "=", "user2")
            .orderBy("pinnedAt", "desc")
            .execute();

        expect(rows.map((r: any) => r.sessionId)).toEqual(["sessC", "sessB", "sessA"]);
    });

    test("pins are scoped to user — different users don't see each other's pins", async () => {
        await db
            .insertInto("user_pinned_session")
            .values({ userId: "userX", sessionId: "sessX", pinnedAt: new Date().toISOString() })
            .execute();

        const rowsY = await db
            .selectFrom("user_pinned_session")
            .select("sessionId")
            .where("userId", "=", "userY")
            .execute();

        expect(rowsY).toHaveLength(0);
    });
});
