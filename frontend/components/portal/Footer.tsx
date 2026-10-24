import Link from "next/link";

import { Logo } from "../brand/Logo";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div>
          <Logo size={26} />
          <p className="hint">Enter the game. Own the moment.</p>
        </div>
        <nav aria-label="Footer" className="footer-links">
          <Link href="/games">Games</Link>
          <Link href="/brain-clash">Brain Clash</Link>
          <Link href="/beat-drop">Beat Drop</Link>
          <Link href="/story-forge">Story Forge</Link>
          <Link href="/whos-talking">Who&apos;s Talking?</Link>
          <Link href="/#how">How it works</Link>
          <Link href="/#faq">FAQ</Link>
        </nav>
        <p className="hint footer-note">
          Original artwork. Built-in voices from LibriSpeech (CC BY 4.0). Your voice, your victory.
        </p>
      </div>
    </footer>
  );
}
