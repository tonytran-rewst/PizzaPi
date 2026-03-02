// ============================================================================
// /hub namespace — Session list feed (read-only for clients)
//
// Hub is a read-only feed. Clients connect to receive the live session list
// and status updates. All broadcasts are triggered by sio-registry when
// sessions are added/removed/updated.
// ============================================================================

import type { Server as SocketIOServer, Namespace } from "socket.io";
import type {
    HubClientToServerEvents,
    HubServerToClientEvents,
    HubInterServerEvents,
    HubSocketData,
} from "@pizzapi/protocol";
import { sessionCookieAuthMiddleware } from "./auth.js";
import {
    addHubClient,
    removeHubClient,
    getSessions,
} from "../sio-registry.js";
import { getPinnedSessionIds } from "../../sessions/pinned.js";

export function registerHubNamespace(io: SocketIOServer): void {
    const hub: Namespace<
        HubClientToServerEvents,
        HubServerToClientEvents,
        HubInterServerEvents,
        HubSocketData
    > = io.of("/hub");

    // Auth: validate session cookie from handshake
    hub.use(sessionCookieAuthMiddleware() as Parameters<typeof hub.use>[0]);

    hub.on("connection", async (socket) => {
        const userId = socket.data.userId ?? "";

        console.log(`[sio/hub] connected: ${socket.id} userId=${userId}`);

        // Join hub room (filtered by user)
        await addHubClient(socket, userId);

        // Send initial session list for this user, enriched with pin status
        const sessions = await getSessions(userId);
        let pinnedIds: Set<string>;
        try {
            pinnedIds = new Set(await getPinnedSessionIds(userId));
        } catch {
            pinnedIds = new Set();
        }
        const enriched = sessions.map((s) => ({
            ...s,
            isPinned: pinnedIds.has(s.sessionId),
        }));
        socket.emit("sessions", { sessions: enriched });

        // ── disconnect ───────────────────────────────────────────────────────
        socket.on("disconnect", async (reason) => {
            console.log(`[sio/hub] disconnected: ${socket.id} (${reason})`);
            await removeHubClient(socket, userId);
        });
    });
}
