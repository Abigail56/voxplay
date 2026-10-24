"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthStore } from "@/store/useAuthStore";

import { Art } from "../art/Scenes";
import { Loader } from "../brand/Loader";
import { AuthForm } from "./AuthForm";

/** Only same-site paths, so a crafted link can't bounce players to another website. */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/games";
}

export function SignIn() {
  const router = useRouter();
  const { me, ready, restore, signOut } = useAuthStore();
  const [next, setNext] = useState("/games");

  useEffect(() => {
    restore();
    setNext(safeNext(new URLSearchParams(window.location.search).get("next")));
  }, [restore]);

  if (!ready) return <Loader />;
  return (
    <div className="welcome">
      <section className="hero">
        <div className="hero-banner">
          <Art slot="hero" className="art-fill" />
        </div>
        <p className="eyebrow">Join VOXPLAY</p>
        <h1>
          Your player. <span className="grad">Every game.</span>
        </h1>
        <p className="lede">
          One player works across every VOXPLAY game. Brain Clash needs nothing else. Who&apos;s Talking? will also ask
          you to record your voice once.
        </p>
        {next !== "/games" && <p className="hint">You&apos;ll go straight back to where you were.</p>}
      </section>
      {me ? (
        <div className="card auth">
          <p className="tagline">
            Signed in as <strong>{me.username}</strong>.
          </p>
          <Link href={next} className="btn primary big">
            Continue
          </Link>
          <button className="link" onClick={signOut}>
            Sign out
          </button>
        </div>
      ) : (
        <AuthForm onDone={() => router.push(next)} />
      )}
    </div>
  );
}
