import Link from "next/link";

import { Art } from "@/components/art/Scenes";
import { Crew } from "@/components/portal/Crew";
import { GameCard } from "@/components/portal/GameCard";
import { LiveResults } from "@/components/portal/LiveResults";
import { LiveStats } from "@/components/portal/LiveStats";
import { GAMES } from "@/lib/games";

const STEPS = [
  { n: "01", title: "Make your player", text: "A name and a password, that's it. (Who's Talking? also asks for three quick voice clips.)" },
  { n: "02", title: "Open a room", text: "Pick a game, get a code like NOVA-42 and drop it in the group chat. Friends join from their own phones." },
  { n: "03", title: "Play live", text: "Questions, hums and scores hit every screen at once. Speak your answer or type it: you've got 20 seconds." },
];

const FEATURES = [
  { icon: "🎙️", title: "Answer with your voice", text: "Speak, and the server turns it into words and checks them. A text box is always there too." },
  { icon: "📱", title: "Every phone is a controller", text: "No console, no download. A room code and a browser is all it takes." },
  { icon: "🌍", title: "Made for here", text: "Questions on African music, Nigerian entertainment, football, food, history and Pidgin." },
  { icon: "🤖", title: "A fair-play AI", text: "It listens to every hum and watches for pasted, copied or looked-up answers. The host has the final say." },
];

const FAQ = [
  {
    q: "What is VOXPLAY?",
    a: "VOXPLAY is a home for live party games you play with friends, each of you on your own phone. Four games are live: Brain Clash (the team quiz), Beat Drop (hum the song, your team names it), Story Forge (build a wild story a line at a time) and Who's Talking? (fool the AI that knows your voice). Questions are about African and Nigerian music, movies, football, food, history and Pidgin, and you can speak your answers or type them.",
  },
  {
    q: "Do I need to download anything?",
    a: "No. VOXPLAY runs in the browser on any phone, tablet or laptop. One person opens a room and shares the code or link (WhatsApp works great), and everyone joins in seconds.",
  },
  {
    q: "Is VOXPLAY free?",
    a: "Yes. It runs on open-source models on the server, with no paid services and no adverts.",
  },
  {
    q: "Do I need an account?",
    a: "You can look around without one. To create or join a room you make a player: just a name and a password. Brain Clash doesn't need any voice setup.",
  },
  {
    q: "How long does a game take?",
    a: "Every round is 20 seconds (the host can change it), so most matches last 5 to 10 minutes. Perfect for a quick rematch, or ten.",
  },
  {
    q: "Can I speak my answers?",
    a: "Yes. Press the mic, say it, press stop: the server turns your words into text and checks them. Small slips and different spellings are fine. Your browser asks for microphone permission the first time, and a text box is always there if you'd rather type.",
  },
  {
    q: "What happens to my voice?",
    a: "Brain Clash turns your spoken answer into text and throws the recording away straight after. Who's Talking? keeps a voiceprint (192 numbers, not a recording) so it can recognise you, and you can delete it any time.",
  },
  {
    q: "How does VOXPLAY stop cheating?",
    a: "The server keeps the score and the clock, so nobody can award themselves points. On top of that a fair-play AI flags anything suspicious: a Beat Drop hummer who says the title, a Story Forge line copied from earlier, or a right answer that came after leaving the game, pasted in or typed impossibly fast. Flagged points wait on hold, everyone sees why, and the host allows or voids them.",
  },
  {
    q: "How many people can play?",
    a: "Brain Clash, Beat Drop and Story Forge need two teams, so at least two players, and work best with a full room of friends, family or classmates (up to 20). Who's Talking? takes up to 12.",
  },
  {
    q: "Can I turn the music off?",
    a: "Yes: tap Music in the top bar. It plays a calm track while you browse and a battle theme in the games, and it fades out by itself whenever someone records or a clip plays.",
  },
  {
    q: "Where can I see the results?",
    a: "Every finished match shows up live under \"Fresh from the arena\" on the home page, with team names and scores (never player names). In the room itself, scores update on every screen the moment points are won.",
  },
];

export default function Landing() {
  const featured = GAMES.find((g) => g.featured)!;
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="on-air" aria-hidden /> Live party games · Play from your phone · Anywhere, any time
          </p>
          <h1>
            Enter your next <span className="grad">universe.</span>
          </h1>
          <p className="lede">
            Grab your phone, open a room and turn any hangout into a showdown. Quiz battles, hum-offs, story duels and
            voice games: loud, fast and made for Africa.
          </p>
          <div className="row hero-actions">
            <Link href="/games" className="btn primary big">
              Play now
            </Link>
            <Link href="/brain-clash#join" className="btn big">
              Join with a code
            </Link>
          </div>
          <p className="hint">Your world. Your voice. Your victory.</p>
          <LiveStats />
        </div>
        <div className="hero-art">
          <Art slot="hero" className="art-fill" priority />
        </div>
      </section>

      <section className="landing-section" aria-labelledby="battle">
        <div className="section-title">
          <p className="eyebrow">The games</p>
          <h2 id="battle">Choose your battle</h2>
        </div>
        <div className="game-grid">
          {GAMES.map((g) => (
            <GameCard key={g.id} game={g} />
          ))}
        </div>
      </section>

      <section className="landing-section" aria-labelledby="results-title">
        <div className="section-title">
          <p className="eyebrow">
            <span className="live-dot" aria-hidden /> Live results
          </p>
          <h2 id="results-title">Fresh from the arena</h2>
        </div>
        <LiveResults />
      </section>

      <section className="featured" aria-labelledby="featured">
        <div className="featured-art">
          <Art slot={featured.art} className="art-fill" />
        </div>
        <div className="featured-copy">
          <p className="eyebrow">Featured game</p>
          <h2 id="featured">{featured.title}</h2>
          <p className="game-tagline">{featured.tagline}</p>
          <p>{featured.description}</p>
          <ul className="mode-chips">
            <li>Brain Battle</li>
            <li>Name It Fast</li>
            <li>Quick-Fire</li>
            <li>Word Association</li>
          </ul>
          <div className="row">
            <Link href="/brain-clash" className="btn primary big">
              Enter the arena
            </Link>
            <Link href="/brain-clash#categories" className="btn big">
              See all 16 categories
            </Link>
          </div>
        </div>
      </section>

      <section className="landing-section" aria-labelledby="crew-title">
        <div className="section-title">
          <p className="eyebrow">The crew</p>
          <h2 id="crew-title">Meet your captains</h2>
        </div>
        <Crew />
      </section>

      <section className="landing-section" id="how" aria-labelledby="how-title">
        <div className="section-title">
          <p className="eyebrow">How it works</p>
          <h2 id="how-title">From zero to game night in a minute</h2>
        </div>
        <ol className="steps-row">
          {STEPS.map((s) => (
            <li key={s.n}>
              <span className="step-n">{s.n}</span>
              <h3>{s.title}</h3>
              <p className="hint">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-section" aria-labelledby="features-title">
        <div className="section-title">
          <p className="eyebrow">Play with friends</p>
          <h2 id="features-title">Built for the group chat</h2>
        </div>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature">
              <span className="feature-icon" aria-hidden>
                {f.icon}
              </span>
              <h3>{f.title}</h3>
              <p className="hint">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section" id="faq" aria-labelledby="faq-title">
        <div className="section-title">
          <p className="eyebrow">Questions</p>
          <h2 id="faq-title">FAQ</h2>
        </div>
        <div className="faq">
          {FAQ.map((f) => (
            <details key={f.q}>
              <summary>{f.q}</summary>
              <p className="hint">{f.a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
