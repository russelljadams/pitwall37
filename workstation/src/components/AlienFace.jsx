/**
 * AlienFace — SVG animated alien head (MGS codec style).
 * Self-contained, no external assets.
 */
export function AlienFace({ speaking = false, toolActive = false }) {
  return (
    <svg
      class="ac-face-svg"
      viewBox="0 0 100 120"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient id="alien-glow-grad" cx="50%" cy="40%" r="50%">
          <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.3" />
          <stop offset="100%" stop-color="#06b6d4" stop-opacity="0" />
        </radialGradient>
        <radialGradient id="alien-eye-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#111" />
          <stop offset="60%" stop-color="#0a0a0a" />
          <stop offset="100%" stop-color="#06b6d4" stop-opacity="0.3" />
        </radialGradient>
        <filter id="alien-eye-glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Ambient glow */}
      <ellipse
        class="alien-glow"
        cx="50" cy="50"
        rx="45" ry="55"
        fill="url(#alien-glow-grad)"
      />

      {/* Head group with breathing animation */}
      <g class="alien-head">
        {/* Skull shape — elongated, smooth */}
        <path
          d="M50 8 C25 8, 12 30, 14 55 C15 70, 22 85, 35 95 C40 99, 45 102, 50 103 C55 102, 60 99, 65 95 C78 85, 85 70, 86 55 C88 30, 75 8, 50 8 Z"
          fill="#1a2a2a"
          stroke="#0891b2"
          stroke-width="0.5"
          opacity="0.9"
        />

        {/* Inner skull detail */}
        <path
          d="M50 14 C30 14, 19 33, 20 53 C21 66, 26 78, 37 88 C42 92, 46 94, 50 95 C54 94, 58 92, 63 88 C74 78, 79 66, 80 53 C81 33, 70 14, 50 14 Z"
          fill="#111a1a"
          opacity="0.6"
        />

        {/* Left eye */}
        <g class={`alien-eye ${toolActive ? 'glowing' : ''}`}>
          <ellipse
            cx="36" cy="50"
            rx="13" ry="10"
            fill="url(#alien-eye-grad)"
            stroke="#0891b2"
            stroke-width="0.5"
            filter={toolActive ? 'url(#alien-eye-glow)' : undefined}
          />
          {/* Eye highlight */}
          <ellipse
            cx="33" cy="47"
            rx="3" ry="2"
            fill="#06b6d4"
            opacity="0.2"
          />
          {/* Eye lid for blink */}
          <ellipse
            class="alien-eye-lid"
            cx="36" cy="50"
            rx="13" ry="10"
            fill="#1a2a2a"
            opacity="0"
          >
            <animate
              attributeName="opacity"
              values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;0"
              dur="6s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="ry"
              values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;10;0"
              dur="6s"
              repeatCount="indefinite"
            />
          </ellipse>
        </g>

        {/* Right eye */}
        <g class={`alien-eye ${toolActive ? 'glowing' : ''}`}>
          <ellipse
            cx="64" cy="50"
            rx="13" ry="10"
            fill="url(#alien-eye-grad)"
            stroke="#0891b2"
            stroke-width="0.5"
            filter={toolActive ? 'url(#alien-eye-glow)' : undefined}
          />
          <ellipse
            cx="61" cy="47"
            rx="3" ry="2"
            fill="#06b6d4"
            opacity="0.2"
          />
          <ellipse
            class="alien-eye-lid"
            cx="64" cy="50"
            rx="13" ry="10"
            fill="#1a2a2a"
            opacity="0"
          >
            <animate
              attributeName="opacity"
              values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;0"
              dur="6s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="ry"
              values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;10;0"
              dur="6s"
              repeatCount="indefinite"
            />
          </ellipse>
        </g>

        {/* Nose — subtle slits */}
        <line x1="48" y1="66" x2="48" y2="72" stroke="#0891b2" stroke-width="0.4" opacity="0.4" />
        <line x1="52" y1="66" x2="52" y2="72" stroke="#0891b2" stroke-width="0.4" opacity="0.4" />

        {/* Mouth */}
        <g class={`alien-mouth ${speaking ? 'speaking' : ''}`}>
          {speaking ? (
            <ellipse
              cx="50" cy="82"
              rx="6" ry="3"
              fill="#0a1515"
              stroke="#0891b2"
              stroke-width="0.4"
            >
              <animate
                attributeName="ry"
                values="1;3;2;4;1;3;2"
                dur="0.4s"
                repeatCount="indefinite"
              />
            </ellipse>
          ) : (
            <path
              d="M43 82 Q50 85, 57 82"
              fill="none"
              stroke="#0891b2"
              stroke-width="0.5"
              opacity="0.5"
            />
          )}
        </g>

        {/* Cranium ridges */}
        <path
          d="M35 20 Q50 12, 65 20"
          fill="none"
          stroke="#0891b2"
          stroke-width="0.3"
          opacity="0.2"
        />
        <path
          d="M30 28 Q50 18, 70 28"
          fill="none"
          stroke="#0891b2"
          stroke-width="0.3"
          opacity="0.15"
        />
      </g>
    </svg>
  );
}
