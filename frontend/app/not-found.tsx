import Link from "next/link";

export const metadata = { title: "Lost in the Nexus" };

export default function NotFound() {
  return (
    <section className="state-page">
      <p className="kicker">Error 404</p>
      <h1>Lost in the Nexus</h1>
      <p className="tagline">This portal doesn&apos;t lead anywhere. The game you were looking for may have ended, or the link has a typo.</p>
      <Link href="/" className="btn primary big">
        Back to VOXPLAY
      </Link>
    </section>
  );
}
