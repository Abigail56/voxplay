"use client";

import { useEffect, useRef } from "react";

import { liveUrl } from "./api";

type Handlers = {
  onDashboard?: () => void;
  onRoom?: () => void;
  onReaction?: (emoji: string, from: string) => void;
  onSignedOut?: () => void;
};

/** Live updates over a WebSocket. The server only says what changed; handlers refetch.
 *  Reconnects with back-off, and pings every 15 s so the player shows as online. */
export function useLive(token: string | null, room: string | null, handlers: Handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    if (!token) return;
    let ws: WebSocket | null = null;
    let ping: ReturnType<typeof setInterval> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let stopped = false;

    const connect = () => {
      ws = new WebSocket(liveUrl(token, room));
      ws.onopen = () => {
        attempts = 0;
        // Catch up on anything that changed while we were disconnected.
        ref.current.onDashboard?.();
        ref.current.onRoom?.();
        ping = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "ping" })), 15_000);
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data) as { type: string; reaction?: string; from?: string };
        if (msg.type === "dashboard") ref.current.onDashboard?.();
        if (msg.type === "room") ref.current.onRoom?.();
        if (msg.type === "reaction" && msg.reaction) ref.current.onReaction?.(msg.reaction, msg.from ?? "");
      };
      ws.onclose = (e) => {
        clearInterval(ping);
        if (stopped) return;
        if (e.code === 4401) return ref.current.onSignedOut?.();
        retry = setTimeout(connect, Math.min(15_000, 1000 * 2 ** attempts++));
      };
    };
    connect();

    return () => {
      stopped = true;
      clearInterval(ping);
      clearTimeout(retry);
      ws?.close();
    };
  }, [token, room]);
}
