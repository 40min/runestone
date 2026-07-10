import React from "react";
import { Diamond } from "lucide-react";

interface AuthLayoutProps {
  children: React.ReactNode;
}

/** Decorative floating gemstone SVG used in the left panel. */
const GemstoneIllustration: React.FC = () => (
  <svg
    viewBox="0 0 200 200"
    width="180"
    height="180"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <defs>
      <radialGradient id="gemGlow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="#38e07b" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#38e07b" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="gemFace1" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#6effa8" />
        <stop offset="100%" stopColor="#1db954" />
      </linearGradient>
      <linearGradient id="gemFace2" x1="100%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#2ecc71" />
        <stop offset="100%" stopColor="#0d6e36" />
      </linearGradient>
      <linearGradient id="gemFace3" x1="50%" y1="0%" x2="50%" y2="100%">
        <stop offset="0%" stopColor="#a8ffd4" stopOpacity="0.9" />
        <stop offset="100%" stopColor="#38e07b" stopOpacity="0.6" />
      </linearGradient>
      <filter id="gemShadow" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#38e07b" floodOpacity="0.4" />
      </filter>
    </defs>
    {/* Glow circle */}
    <ellipse cx="100" cy="150" rx="70" ry="20" fill="url(#gemGlow)" />
    {/* Shadow / base ellipse */}
    <ellipse cx="100" cy="160" rx="50" ry="10" fill="#38e07b" opacity="0.12" />
    {/* Gem body — classic 8-point cut */}
    <g filter="url(#gemShadow)">
      {/* Top facets */}
      <polygon points="100,50 130,90 100,80 70,90" fill="url(#gemFace3)" opacity="0.95" />
      {/* Left side */}
      <polygon points="70,90 100,80 100,140 60,120" fill="url(#gemFace2)" />
      {/* Right side */}
      <polygon points="130,90 100,80 100,140 140,120" fill="url(#gemFace1)" />
      {/* Bottom left */}
      <polygon points="60,120 100,140 100,155" fill="#0d6e36" opacity="0.9" />
      {/* Bottom right */}
      <polygon points="140,120 100,140 100,155" fill="#1db954" opacity="0.8" />
      {/* Top highlight */}
      <polygon points="100,50 115,75 100,80 85,75" fill="white" opacity="0.25" />
    </g>
    {/* Sparkle dots */}
    <circle cx="55" cy="70" r="2.5" fill="#38e07b" opacity="0.7" />
    <circle cx="148" cy="85" r="1.8" fill="#38e07b" opacity="0.5" />
    <circle cx="80" cy="45" r="1.5" fill="#38e07b" opacity="0.4" />
  </svg>
);

/**
 * Full-page two-column auth shell. Left side has branded content and an
 * illustration; right side renders the passed form panel.
 */
const AuthLayout: React.FC<AuthLayoutProps> = ({ children }) => (
  <div className="auth-page">
    <div className="auth-shell">
      {/* ── Left branding panel ─────────────────────────────────── */}
      <div className="auth-left">
        {/* Top-left wordmark */}
        <div className="auth-wordmark">
          <Diamond size={22} style={{ color: "var(--primary-color)" }} />
          <span className="auth-wordmark-text">Runestone</span>
        </div>

        <div className="auth-left-content">
          {/* Green pill badge */}
          <div className="auth-badge">
            <span className="auth-badge-icon">✦</span>
            <span>RUNESTONE</span>
          </div>

          <h1 className="auth-welcome">Welcome back</h1>
          <p className="auth-tagline">Sign in. Another rune. Another stone.</p>

          <div className="auth-illustration">
            <GemstoneIllustration />
          </div>
        </div>
      </div>

      {/* ── Right form panel ────────────────────────────────────── */}
      <div className="auth-right">
        <div className="auth-card">{children}</div>
      </div>
    </div>
  </div>
);

export default AuthLayout;
