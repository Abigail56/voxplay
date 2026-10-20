"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, SignedOutError, type Dashboard, type Room } from "@/lib/api";
import { loadSoundSetting, saveSoundSetting, sfx } from "@/lib/game";
import { useLive } from "@/lib/useLive";
import { useAuthStore } from "@/store/useAuthStore";

import { DailyChallenge } from "./DailyChallenge";
import { Leaderboards } from "./Leaderboards";
import { Lobby } from "./Lobby";
import { PlayerCard } from "./PlayerCard";
import { RoomPanel, type Reaction } from "./RoomPanel";
import { VoiceSetup } from "./VoiceSetup";
import { Welcome } from "./Welcome";
import { World } from "./World";

/** The whole game: title screen → voice setup → dashboard + lobby / room. */
export function GameHome() {
  const { token, me, ready, restore, refreshMe, signOut } = useAuthStore();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [roomCode, setRoomCode] = useState<string | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  // The room we're in *now*, so a slow reply about a room we've just left can't bring it back.
  const codeRef = useRef<string | null>(null);
  codeRef.current = roomCode;
  const [sound, setSound] = useState(true);
  const [reactions, setReactions] = useState<Reaction[]>([]);
  // Bumped on every dashboard update, so the daily board and leaderboards refetch too.
  const [refreshKey, setRefreshKey] = useState(0);
  // From an invite link like /?join=TIGER-42: joined as soon as the player is ready.
  const [invite, setInvite] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  useEffect(() => {
    restore();
    setSound(loadSoundSetting());
    setInvite(new URLSearchParams(window.location.search).get("join")?.toUpperCase() ?? null);
  }, [restore]);

  // Any request answered with 401 (expired token, restarted dev server) → back to the title screen.
  const guard = useCallback(
    async <T,>(p: Promise<T>): Promise<T | undefined> => {
      try {
        return await p;
      } catch (e) {
        if (e instanceof SignedOutError) signOut();
        return undefined;
      }
    },
    [signOut],
  );

  const loadDashboard = useCallback(async () => {
    const d = await guard(api.dashboard());
    if (!d) return;
    setDashboard(d);
    setRefreshKey((k) => k + 1);
    // Rejoin the game we're in (after a reload, or when we joined from another tab).
    const mine = d.players.find((p) => p.user_id === d.me)?.room_code;
    if (mine) setRoomCode((c) => c ?? mine);
    refreshMe().catch(() => {});
  }, [guard, refreshMe]);

  const loadRoom = useCallback(async () => {
    const code = roomCode;
    if (!code) return setRoom(null);
    try {
      const r = await api.room(code);
      if (codeRef.current === code) setRoom(r);
    } catch (e) {
      if (e instanceof SignedOutError) return signOut();
      if (codeRef.current !== code) return;
      setRoomCode(null); // the game ended and expired, or was closed
      setRoom(null);
    }
  }, [roomCode, signOut]);

  useEffect(() => {
    if (token && me?.has_voice) loadDashboard();
  }, [token, me?.has_voice, loadDashboard]);
  useEffect(() => {
    loadRoom();
  }, [loadRoom]);
  // A slow fallback in case live updates are blocked by a proxy.
  useEffect(() => {
    if (!token) return;
    const id = setInterval(loadDashboard, 30_000);
    return () => clearInterval(id);
  }, [token, loadDashboard]);

  // Use the invite once the player is signed in and has a voice.
  useEffect(() => {
    if (!invite || !token || !me?.has_voice) return;
    setInvite(null);
    window.history.replaceState(null, "", window.location.pathname); // so a reload doesn't rejoin
    api
      .joinRoom(invite)
      .then(enter)
      .catch((e) => setInviteError(`Couldn't join ${invite}: ${(e as Error).message}`));
  }, [invite, token, me?.has_voice]); // enter() only sets state, so it needn't be a dependency

  useLive(me?.has_voice ? token : null, roomCode, {
    onDashboard: loadDashboard,
    onRoom: loadRoom,
    onSignedOut: signOut,
    onReaction: (emoji, from) => {
      const id = Date.now() + Math.random();
      setReactions((rs) => [...rs.slice(-20), { id, emoji, from }]);
      setTimeout(() => setReactions((rs) => rs.filter((r) => r.id !== id)), 2600);
    },
  });

  function enter(r: Room | null) {
    if (r && r.code !== roomCode) sfx("join", sound);
    codeRef.current = r?.code ?? null;
    setRoom(r);
    setRoomCode(r?.code ?? null);
    loadDashboard();
  }

  function toggleSound() {
    setSound((s) => {
      saveSoundSetting(!s);
      return !s;
    });
  }

  if (!ready) return <p className="hint">Loading…</p>;
  if (!token || !me) return <Welcome invite={invite} />;
  if (!me.has_voice) {
    return (
      <div className="setup-page">
        <h1>Nice to meet you, {me.username}.</h1>
        <p className="tagline">
          One more thing before you play: the game needs to hear your voice.
          {invite && (
            <>
              {" "}
              Then you&apos;ll join game <strong className="code">{invite}</strong>.
            </>
          )}
        </p>
        <VoiceSetup onDone={loadDashboard} />
        <button className="link" onClick={signOut}>
          Sign out
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="topbar">
        <span className="hint">
          Hi <strong>{me.username}</strong>, ready to play?
        </span>
        <button className="btn small ghost" onClick={toggleSound} aria-pressed={sound}>
          {sound ? "Sound on" : "Sound off"}
        </button>
      </div>

      {inviteError && <p className="error">{inviteError}</p>}
      <div className="game-layout">
        <div className="game-main">
          {room && room.code === roomCode ? <RoomPanel room={room} me={me} sound={sound} reactions={reactions} onRoom={enter} /> : <Lobby dashboard={dashboard} onEnter={enter} />}
        </div>
        <aside className="side">
          <PlayerCard me={me} />
          <DailyChallenge sound={sound} refreshKey={refreshKey} onPlayed={loadDashboard} />
        </aside>
      </div>

      <Leaderboards refreshKey={refreshKey} />
      {dashboard && <World dashboard={dashboard} />}

      <footer>
        <strong>Privacy:</strong> your voiceprint (192 numbers, not a recording) is used only for this game. Your city
        is shown only if you turn it on, rounded to about 10 km, and is deleted after 30 days or when you turn it off.
        Deleting your player deletes everything.
      </footer>
    </>
  );
}
