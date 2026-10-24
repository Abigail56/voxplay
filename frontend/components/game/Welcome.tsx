"use client";

import { AuthForm } from "../auth/AuthForm";

/** The title screen: what the game is, plus sign up / sign in. */
export function Welcome({ invite }: { invite: string | null }) {
  return (
    <div className="welcome">
      <section className="hero">
        {invite && (
          <p className="invite-banner">
            You&apos;ve been invited to game <strong className="code">{invite}</strong>. Make a player (or sign in) and
            you&apos;ll go straight in.
          </p>
        )}
        <p className="kicker">
          <span className="on-air" aria-hidden /> A VOXPLAY voice game
        </p>
        <h1>
          Who&apos;s <em>Talking?</em>
        </h1>
        <p className="tagline">
          Everyone records their voice, then you take turns reading silly lines out loud while the game works out
          who&apos;s speaking. It&apos;s usually right. Your job is to make it wrong.
        </p>
        <ol className="how">
          <li>
            <strong>Record three short clips</strong> so the game learns your voice.
          </li>
          <li>
            <strong>Share a game code</strong> with friends. Everyone plays on their own phone.
          </li>
          <li>
            <strong>On your turn</strong>, read the line on screen (&ldquo;the sleepy penguin stole my shiny
            pizzas&rdquo;). Sound like yourself, do an impression, put on a disguise, hide in Guess Who, or pass a voice
            down a broken telephone.
          </li>
          <li>
            <strong>Every point counts</strong> towards the weekly cup and your country&apos;s total. No one around?
            Play solo against the built-in voices.
          </li>
        </ol>
      </section>

      <AuthForm />
    </div>
  );
}
