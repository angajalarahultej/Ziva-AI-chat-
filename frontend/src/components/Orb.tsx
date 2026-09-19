import { motion } from "framer-motion";
import type { AstraState } from "../types";
import { Particles } from "./Particles";

const COLORS: Record<string, string> = {
  OFFLINE: "#3a4358", INITIALIZING: "#e0a100", ONLINE: "#2dd4bf",
  LISTENING: "#34d399", PROCESSING: "#e0a100",
  SPEAKING: "#a78bfa", INTERRUPTED: "#f87171", ERROR: "#f87171",
};

/**
 * Iridescent chrome bubble (from the reference render): pearl base,
 * slowly flowing pastel swirls, glossy streaks + specular dot,
 * crescent bounce-light, gentle float. Breathes with the voice.
 */
export function Orb({ state, level }: { state: AstraState; level: number }) {
  const color = COLORS[state] ?? "#2dd4bf";
  const active = state === "LISTENING" || state === "SPEAKING";
  const breathe = 1 + (active ? level * 0.16 : 0);

  return (
    <div className="relative flex items-center justify-center" style={{ height: 300 }}>
      {/* atoms streaming off the ball */}
      <Particles active={active} />
      {/* soft state aura behind the chrome */}
      <motion.div
        className="absolute rounded-full blur-3xl"
        style={{ width: 260, height: 260, background: `${color}30` }}
        animate={{ scale: breathe, opacity: active ? 0.9 : 0.55 }}
        transition={{ type: "spring", stiffness: 90, damping: 16 }}
      />

      <motion.div
        style={{ width: "min(58vw, 200px)" }}
        animate={{ scale: breathe, y: [0, -12, 0] }}
        transition={{
          scale: { type: "spring", stiffness: 120, damping: 14 },
          y: { duration: 5, repeat: Infinity, ease: "easeInOut" },
        }}
      >
        <svg viewBox="0 0 400 400" className="h-auto w-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <clipPath id="ballClip">
              <circle cx="200" cy="200" r="148" />
            </clipPath>
            {/* pearl base */}
            <radialGradient id="pearl" cx="42%" cy="34%" r="80%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="35%" stopColor="#eef2ff" />
              <stop offset="70%" stopColor="#dcd6f7" />
              <stop offset="100%" stopColor="#b8b3d9" />
            </radialGradient>
            {/* roundness shading */}
            <radialGradient id="shade" cx="50%" cy="50%" r="50%">
              <stop offset="72%" stopColor="#1e1b3a" stopOpacity="0" />
              <stop offset="92%" stopColor="#2a2350" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#141226" stopOpacity="0.55" />
            </radialGradient>
            <radialGradient id="topLight" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="crescent" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#67e8f9" stopOpacity="0" />
              <stop offset="50%" stopColor="#ffffff" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#f9a8d4" stopOpacity="0" />
            </linearGradient>
            {/* slow melting flow for the swirls */}
            <filter id="swirlFlow" x="-20%" y="-20%" width="140%" height="140%">
              <feTurbulence type="fractalNoise" baseFrequency="0.012 0.016" numOctaves="2" seed="4" result="n">
                <animate attributeName="baseFrequency" values="0.012 0.016;0.016 0.021;0.012 0.016"
                  dur="11s" repeatCount="indefinite" />
              </feTurbulence>
              <feDisplacementMap in="SourceGraphic" in2="n" scale="26" xChannelSelector="R" yChannelSelector="G" />
            </filter>
            <filter id="soft" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="16" />
            </filter>
            <filter id="softSm" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="6" />
            </filter>
          </defs>

          {/* base sphere */}
          <circle cx="200" cy="200" r="148" fill="url(#pearl)" />

          {/* ═══ flowing pastel swirls, clipped to the ball ═══ */}
          <g clipPath="url(#ballClip)" filter="url(#swirlFlow)">
            <g filter="url(#soft)">
              <g>
                <animateTransform attributeName="transform" type="rotate"
                  from="0 200 200" to="360 200 200" dur="26s" repeatCount="indefinite" />
                <ellipse cx="150" cy="130" rx="95" ry="70" fill="#f9a8d4" opacity="0.75" />
                <ellipse cx="260" cy="120" rx="80" ry="60" fill="#c4b5fd" opacity="0.7" />
                <ellipse cx="120" cy="250" rx="90" ry="65" fill="#67e8f9" opacity="0.75" />
                <ellipse cx="270" cy="260" rx="85" ry="60" fill="#e879f9" opacity="0.6" />
                <ellipse cx="200" cy="200" rx="70" ry="55" fill="#fed7aa" opacity="0.55" />
              </g>
              <g>
                <animateTransform attributeName="transform" type="rotate"
                  from="360 200 200" to="0 200 200" dur="34s" repeatCount="indefinite" />
                <ellipse cx="230" cy="160" rx="70" ry="50" fill="#6ee7b7" opacity="0.55" />
                <ellipse cx="150" cy="220" rx="60" ry="45" fill="#fdba74" opacity="0.5" />
                <ellipse cx="250" cy="230" rx="75" ry="50" fill="#7dd3fc" opacity="0.6" />
                <ellipse cx="180" cy="110" rx="65" ry="45" fill="#f0abfc" opacity="0.6" />
              </g>
            </g>
            {/* milky white core light */}
            <ellipse cx="185" cy="150" rx="80" ry="65" fill="#ffffff" opacity="0.5" filter="url(#soft)" />
          </g>

          {/* roundness shading + top light */}
          <circle cx="200" cy="200" r="148" fill="url(#shade)" />
          <ellipse cx="170" cy="120" rx="110" ry="80" fill="url(#topLight)" opacity="0.35" />

          {/* glossy streaks */}
          <g filter="url(#softSm)">
            <path d="M110,110 C140,80 190,62 240,66" fill="none"
              stroke="#ffffff" strokeWidth="10" strokeLinecap="round" opacity="0.75" />
            <path d="M92,190 C100,150 115,120 138,100" fill="none"
              stroke="#a5f3fc" strokeWidth="6" strokeLinecap="round" opacity="0.6" />
            {/* bottom crescent bounce-light */}
            <path d="M120,292 C170,318 250,318 296,282" fill="none"
              stroke="url(#crescent)" strokeWidth="9" strokeLinecap="round" opacity="0.85" />
          </g>

          {/* rim: bright crown, soft dark base for depth */}
          <g filter="url(#softSm)">
            <path d="M78,160 C82,90 140,48 210,50" fill="none"
              stroke="#ffffff" strokeWidth="4" strokeLinecap="round" opacity="0.9" />
            <path d="M322,240 C300,290 230,322 160,308" fill="none"
              stroke="#3b3560" strokeWidth="5" strokeLinecap="round" opacity="0.7" />
          </g>
        </svg>
      </motion.div>

      {/* state label */}
      <div
        className="absolute -bottom-1 text-[11px] font-medium tracking-[0.35em]"
        style={{ color }}
      >
        {state === "OFFLINE" ? "OFFLINE" : state}
        {state === "LISTENING" && <span className="pulse-dot"> ●</span>}
      </div>
    </div>
  );
}
