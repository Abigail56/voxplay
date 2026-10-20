"use client";

import { useEffect, useState } from "react";

/** How friends get the game code: the phone's share menu, WhatsApp, or copy the link/code. */
export function Invite({ code }: { code: string }) {
  const [link, setLink] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [canShare, setCanShare] = useState(false);

  useEffect(() => {
    setLink(`${window.location.origin}/?join=${encodeURIComponent(code)}`);
    setCanShare(typeof navigator.share === "function");
  }, [code]);

  const message = `Play "Who's Talking?" with me! Join game ${code}: ${link}`;

  async function copy(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied("The browser blocked copying. Long-press the code to copy it.");
    }
  }

  return (
    <div className="invite">
      <div className="row">
        {canShare && (
          <button
            className="btn small primary"
            onClick={() => navigator.share({ title: "Who's Talking?", text: message, url: link }).catch(() => {})}
          >
            Share invite
          </button>
        )}
        <a className="btn small whatsapp" href={`https://wa.me/?text=${encodeURIComponent(message)}`} target="_blank" rel="noreferrer">
          WhatsApp
        </a>
        <button className="btn small" onClick={() => copy(link, "Link copied!")}>
          Copy link
        </button>
        <button className="btn small ghost" onClick={() => copy(code, "Code copied!")}>
          Copy code
        </button>
      </div>
      {copied && <p className="hint">{copied}</p>}
    </div>
  );
}
