import { GameCard } from "@/components/portal/GameCard";
import { GAMES } from "@/lib/games";

export const metadata = { title: "Games", description: "Every VOXPLAY game: Brain Clash, Who's Talking? and what's coming next." };

export default function Games() {
  return (
    <div className="landing">
      <section className="landing-section">
        <div className="section-title">
          <p className="eyebrow">The games</p>
          <h1 className="page-title">Choose your battle</h1>
          <p className="lede">Pick a game, open a room and send the code to your friends. Games marked Coming soon aren&apos;t playable yet.</p>
        </div>
        <div className="game-grid">
          {GAMES.map((g) => (
            <GameCard key={g.id} game={g} />
          ))}
        </div>
      </section>
    </div>
  );
}
