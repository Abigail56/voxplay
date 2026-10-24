import Link from "next/link";

import { Art } from "@/components/art/Scenes";
import { GameCard } from "@/components/portal/GameCard";
import { GAMES } from "@/lib/games";

const STEPS = [
  { n: "01", title: "Make your player", text: "Pick a name and you're in. Voice games ask you to record a few short clips first." },
  { n: "02", title: "Open a room", text: "Choose a game and get a room code. Friends join from their own phones with the code or a link." },
  { n: "03", title: "Play live", text: "Everyone sees every question, answer and score at the same moment. Speak your answers or type them." },
];

const FEATURES = [
  { icon: "🎙️", title: "Answer with your voice", text: "Speak, and the server turns it into words and checks them. A text box is always there too." },
  { icon: "📱", title: "Every phone is a controller", text: "No console, no download. A room code and a browser is all it takes." },
  { icon: "🌍", title: "Made for here", text: "Questions on African music, Nigerian entertainment, football, food, history and Pidgin." },
  { icon: "🤖", title: "A fair-play AI", text: "It listens to every hum and watches for pasted, copied or looked-up answers. The host has the final say." },
];

const FAQ = [
  {
    q: "Is VOXPLAY free?",
    a: "Yes. It runs on open-source models on the server, with no paid services and no adverts.",
  },
  {
    q: "Do I need an account?",
    a: "You can look around without one. To create or join a room you make a player: just a name and a password. Brain Clash doesn't need any voice setup.",
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
];

export default function Landing() {
  const featured = GAMES.find((g) => g.featured)!;
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="on-air" aria-hidden /> Enter the game. Own the moment.
          </p>
          <h1>
            Enter your next <span className="grad">universe.</span>
          </h1>
          <p className="lede">
            VOXPLAY is a social gaming universe. Open a room, bring your friends and battle it out in team quizzes and
            voice games, each of you playing from your own phone.
          </p>
          <div className="row hero-actions">
            <Link href="/games" className="btn primary big">
              Explore games
            </Link>
            <Link href="/brain-clash" className="btn big">
              Play with friends
            </Link>
          </div>
          <p className="hint">Your world. Your voice. Your victory.</p>
        </div>
        <div className="hero-art">
          <Art slot="hero" className="art-fill" />
          <Link href="/brain-clash" className="hero-preview" aria-label="Brain Clash: open the game">
            <span className="eyebrow">Now playing · Brain Clash</span>
            <span className="preview-q">The famous jollof rice rivalry is between Nigeria and which country?</span>
            <span className="preview-score">
              <span className="team a">Team Nova 40</span>
              <span className="vs">VS</span>
              <span className="team b">Team Pulse 30</span>
            </span>
          </Link>
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
          <Link href="/brain-clash" className="btn primary big">
            Enter the arena
          </Link>
        </div>
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
