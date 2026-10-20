"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useAuthStore } from "@/store/useAuthStore";

export function Nav() {
  const path = usePathname();
  const { me, restore } = useAuthStore();

  // Every page needs to know who is signed in (e.g. to show the admin link).
  useEffect(() => {
    restore();
  }, [restore]);

  // The admin console has its own header bar.
  if (path.startsWith("/admin")) return null;

  return (
    <nav className="nav">
      <Link href="/" className="brand">
        <span className="on-air" aria-hidden />
        Who&apos;s Talking?
      </Link>
      <span className="row">
        {me?.is_admin && (
          <Link href="/admin" className="lab-link">
            Admin
          </Link>
        )}
        {path === "/" ? (
          <Link href="/lab" className="lab-link">
            Voice lab
          </Link>
        ) : (
          <Link href="/" className="lab-link">
            ← Back to the game
          </Link>
        )}
      </span>
    </nav>
  );
}
