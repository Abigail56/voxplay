"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useAuthStore } from "@/store/useAuthStore";

import { Logo } from "./brand/Logo";

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
    <header className="nav-bar">
      <nav className="nav" aria-label="Main">
        <Link href="/" className="brand" aria-label="VOXPLAY home">
          <Logo />
        </Link>
        {me?.is_admin && (
          <Link href="/admin" className="nav-link">
            Admin
          </Link>
        )}
      </nav>
    </header>
  );
}
