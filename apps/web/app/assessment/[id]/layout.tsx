"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function AssessmentLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  const pathname = usePathname();
  const id = params.id;
  const base = `/assessment/${id}`;

  const tabs = [
    { href: base, label: "Dashboard" },
    { href: `${base}/evidence`, label: "Evidence" },
    { href: `${base}/report`, label: "Report" },
  ];

  return (
    <div className="dashboard">
      <header className="dash-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", marginRight: 12 }}>⌂</Link>
          Assessment <code style={{ fontSize: 12, color: "var(--accent)" }}>{id}</code>
        </h1>
        <nav className="nav">
          {tabs.map((t) => (
            <Link
              key={t.href}
              href={t.href}
              className={pathname === t.href ? "active" : ""}
            >
              {t.label}
            </Link>
          ))}
        </nav>
      </header>
      {children}
    </div>
  );
}
