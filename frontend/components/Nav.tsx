"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthStore } from "@/store/useAuthStore";

import { Logo } from "./brand/Logo";
import { MusicToggle } from "./MusicToggle";

const LINKS = [
  { href: "/games", label: "Games" },
  { href: "/brain-clash", label: "Brain Clash" },
  { href: "/beat-drop", label: "Beat Drop" },
  { href: "/story-forge", label: "Story Forge" },
  { href: "/whos-talking", label: "Who's Talking?" },
];

export function Nav() {
  const path = usePathname();
  const { me, restore } = useAuthStore();
  const [open, setOpen] = useState(false);

  // Every page needs to know who is signed in (e.g. to show the admin link).
  useEffect(() => {
    restore();
  }, [restore]);
  useEffect(() => setOpen(false), [path]); // close the mobile menu after navigating
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // The admin console has its own header bar.
  if (path.startsWith("/admin")) return null;

  const current = (href: string) => (href === "/" ? path === "/" : !href.includes("#") && path.startsWith(href));

  return (
    <header className="nav-bar">
      <nav className="nav" aria-label="Main">
        <Link href="/" className="brand" aria-label="VOXPLAY home">
          <Logo />
        </Link>
        <MusicToggle />
        <button
          className="menu-toggle"
          aria-expanded={open}
          aria-controls="nav-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((o) => !o)}
        >
          <span aria-hidden>{open ? "✕" : "☰"}</span>
        </button>
        <div id="nav-menu" className={`nav-menu ${open ? "open" : ""}`}>
          <ul className="nav-links">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="nav-link" aria-current={current(l.href) ? "page" : undefined}>
                  {l.label}
                </Link>
              </li>
            ))}
            {me?.is_admin && (
              <li>
                <Link href="/admin" className="nav-link">
                  Admin
                </Link>
              </li>
            )}
          </ul>
          <div className="nav-actions">
            {me ? (
              <span className="nav-user" title="Signed in">
                <span className="presence on" aria-hidden /> {me.username}
              </span>
            ) : (
              <Link href={`/sign-in?next=${encodeURIComponent(path)}`} className="nav-link">
                Sign in
              </Link>
            )}
            <Link href="/brain-clash" className="btn primary small">
              Play now
            </Link>
          </div>
        </div>
      </nav>
    </header>
  );
}
