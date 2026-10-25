import Link from "next/link";

import type { GameInfo } from "@/lib/games";

import { Art } from "../art/Scenes";

/** One game in the catalogue: artwork, what it is, who it's for, and Play or Coming soon. */
export function GameCard({ game }: { game: GameInfo }) {
  const live = game.status === "live";
  return (
    <article className={`game-card ${live ? "" : "soon"}`}>
      <div className="game-art">
        <Art slot={game.art} />
        {!live && <span className="status-pill">Coming soon</span>}
      </div>
      <div className="game-body">
        <span className="eyebrow">{game.category}</span>
        <h3>{game.title}</h3>
        <p className="game-tagline">{game.tagline}</p>
        <p className="hint">{game.description}</p>
        <div className="game-foot">
          <span className="hint">👥 {game.players}</span>
          {live && game.href ? (
            <Link href={game.href} className="btn primary small">
              Play now
            </Link>
          ) : (
            <span className="btn small" aria-disabled="true">
              Coming soon
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
