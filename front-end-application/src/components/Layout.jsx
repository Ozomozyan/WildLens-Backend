// src/components/Layout.jsx
import Navbar from "./Navbar.jsx";

/**
 * @param {boolean} withBg   – show the background image?
 * @param {boolean} overlay  – draw the translucent overlay?
 * @param {string}  overlayClass – Tailwind classes for the overlay colour / opacity
 */
export default function Layout({
  children,
  withBg   = true,
  overlay  = true,
  overlayClass = "bg-black/40",   // 40 % black → change to /20 etc.
}) {
  const bg = withBg ? "bg-page bg-cover bg-fixed bg-center" : "bg-white";

  return (
    <div className={`${bg} relative min-h-screen text-gray-900`}>
      {/* ─── OPTIONAL OVERLAY ───────────────────────────── */}
      {withBg && overlay && (
        <div className={`absolute inset-0 ${overlayClass} pointer-events-none`} />
      )}

      <Navbar />
      <main className="relative z-10">{children}</main>
    </div>
  );
}
