import { GameCard } from "@/components/portal/GameCard";
import { GAMES } from "@/lib/games";

export const metadata = { title: "Games", description: "Every VOXPLAY game: Brain Clash, Beat Drop, Story Forge, Who's Talking? and what's dropping next." };

export default function Games() {
  return (
    <div className="landing">
      <section className="landing-section">
        <div className="section-title">
          <p className="eyebrow">The games</p>
          <h1 className="page-title">Choose your battle</h1>
          <p className="lede">Pick a game, open a room and drop the code in the group chat. Everyone plays from their own phone, 20 seconds a round.</p>
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
