import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  spring,
  useVideoConfig,
  interpolateColors,
} from "remotion";
import { TransitionSeries, springTiming, linearTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { fade } from "@remotion/transitions/fade";
import { noise3D } from "@remotion/noise";

// ─── Palette ────────────────────────────────────────────────────────────────
const BG = "#07070B";
const TEXT = "#EDEDF0";
const MUTED = "#9898A6";
const ACCENT = "#6366F1";
const ACCENT_LIGHT = "#818CF8";
const ACCENT_GLOW = "rgba(99,102,241,0.3)";

// ─── Slide data ─────────────────────────────────────────────────────────────
const SLIDES = [
  {
    image: "screenshots/01-proxies.png",
    title: "Proxy Management",
    subtitle: "Import, monitor & manage thousands of proxies with source tracking",
    number: "01",
    // Ken Burns: slow zoom toward the proxy table
    kb: { endScale: 1.18, originX: "50%", originY: "35%" },
  },
  {
    image: "screenshots/02-dashboard.png",
    title: "Real-Time Dashboard",
    subtitle: "Health rings, provider overview, pool utilization at a glance",
    number: "02",
    kb: { endScale: 1.15, originX: "45%", originY: "40%" },
  },
  {
    image: "screenshots/03-import-modal.png",
    title: "Flexible Import",
    subtitle: "Paste, upload files, or fetch from URLs with auto-polling",
    number: "03",
    kb: { endScale: 1.12, originX: "50%", originY: "50%" },
  },
  {
    image: "screenshots/04-pools.png",
    title: "Pool Rotation",
    subtitle: "Round-robin & random strategies with health-aware routing",
    number: "04",
    kb: { endScale: 1.16, originX: "55%", originY: "30%" },
  },
  {
    image: "screenshots/05-api-docs.png",
    title: "Full REST API",
    subtitle: "Interactive API docs with Redocly — every feature accessible via API",
    number: "05",
    kb: { endScale: 1.14, originX: "50%", originY: "25%" },
  },
];

const SLIDE_DURATION = 135; // 4.5s per slide
const INTRO_DURATION = 105; // 3.5s
const OUTRO_DURATION = 90; // 3s
const TRANSITION_FRAMES = 20; // 0.67s overlap

// ─── Animated dot grid background ───────────────────────────────────────────
const AnimatedGrid: React.FC<{ seed?: string; opacity?: number }> = ({
  seed = "grid",
  opacity = 0.3,
}) => {
  const frame = useCurrentFrame();
  const dots: React.ReactNode[] = [];
  const cols = 32;
  const rows = 18;
  const spacingX = 1920 / cols;
  const spacingY = 1080 / rows;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const baseX = c * spacingX + spacingX / 2;
      const baseY = r * spacingY + spacingY / 2;
      // Subtle noise-driven movement
      const t = frame * 0.008;
      const offsetX = noise3D(seed, c * 0.3, r * 0.3, t) * 6;
      const offsetY = noise3D(seed + "y", c * 0.3, r * 0.3, t) * 6;
      const dotOpacity =
        0.15 + noise3D(seed + "o", c * 0.2, r * 0.2, t * 0.5) * 0.15;

      dots.push(
        <circle
          key={`${r}-${c}`}
          cx={baseX + offsetX}
          cy={baseY + offsetY}
          r={1.5}
          fill={ACCENT_LIGHT}
          opacity={dotOpacity}
        />,
      );
    }
  }

  return (
    <AbsoluteFill style={{ opacity }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080">
        {dots}
      </svg>
    </AbsoluteFill>
  );
};

// ─── macOS browser frame ────────────────────────────────────────────────────
const BrowserFrame: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        borderRadius: 12,
        overflow: "hidden",
        boxShadow:
          "0 25px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)",
        display: "flex",
        flexDirection: "column",
        background: "#1C1C22",
      }}
    >
      {/* Title bar */}
      <div
        style={{
          height: 40,
          background: "linear-gradient(180deg, #2A2A32 0%, #222228 100%)",
          display: "flex",
          alignItems: "center",
          paddingLeft: 16,
          paddingRight: 16,
          gap: 8,
          flexShrink: 0,
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Traffic lights */}
        <div style={{ display: "flex", gap: 7 }}>
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: "#FF5F57",
            }}
          />
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: "#FEBC2E",
            }}
          />
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: "#28C840",
            }}
          />
        </div>
      </div>
      {/* Content */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        {children}
      </div>
    </div>
  );
};

// ─── Staggered word-by-word text ────────────────────────────────────────────
const StaggeredText: React.FC<{
  text: string;
  startFrame: number;
  fontSize: number;
  color: string;
  fontWeight?: number;
  letterSpacing?: string;
  staggerFrames?: number;
}> = ({
  text,
  startFrame,
  fontSize,
  color,
  fontWeight = 700,
  letterSpacing = "-1px",
  staggerFrames = 4,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(" ");

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0 12px" }}>
      {words.map((word, i) => {
        const delay = startFrame + i * staggerFrames;
        const localFrame = Math.max(0, frame - delay);
        const wordOpacity = spring({
          frame: localFrame,
          fps,
          config: { damping: 20, stiffness: 200, mass: 0.5 },
        });
        const wordY = spring({
          frame: localFrame,
          fps,
          from: 25,
          to: 0,
          config: { damping: 18, stiffness: 180 },
        });

        return (
          <span
            key={i}
            style={{
              fontSize,
              fontWeight,
              color,
              fontFamily: "Inter, system-ui, sans-serif",
              letterSpacing,
              opacity: wordOpacity,
              transform: `translateY(${wordY}px)`,
              display: "inline-block",
              textShadow: "0 2px 20px rgba(0,0,0,0.8)",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// ─── Feature slide ──────────────────────────────────────────────────────────
const FeatureSlide: React.FC<{
  image: string;
  title: string;
  subtitle: string;
  number: string;
  kb: { endScale: number; originX: string; originY: string };
}> = ({ image, title, subtitle, number, kb }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Browser frame entrance: 3D tilt to flat
  const frameEntrance = spring({
    frame,
    fps,
    config: { damping: 22, stiffness: 120, mass: 0.8 },
  });
  const frameTiltX = interpolate(frameEntrance, [0, 1], [8, 0]);
  const frameTiltY = interpolate(frameEntrance, [0, 1], [-4, 0]);
  const frameTranslateY = interpolate(frameEntrance, [0, 1], [60, 0]);
  const frameOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Ken Burns: slow continuous zoom
  const kenBurnsScale = interpolate(
    frame,
    [0, SLIDE_DURATION],
    [1.0, kb.endScale],
    { extrapolateRight: "clamp", easing: Easing.out(Easing.quad) },
  );

  // Feature number background
  const numberOpacity = interpolate(frame, [5, 25], [0, 0.06], {
    extrapolateRight: "clamp",
  });

  // Accent line draw
  const lineWidth = interpolate(frame, [20, 50], [0, 80], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Subtitle
  const subtitleOpacity = interpolate(frame, [30, 45], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subtitleY = spring({
    frame: Math.max(0, frame - 28),
    fps,
    from: 15,
    to: 0,
    config: { damping: 20, stiffness: 150 },
  });

  return (
    <AbsoluteFill style={{ background: BG }}>
      {/* Animated grid in background */}
      <AnimatedGrid seed={`slide-${number}`} opacity={0.15} />

      {/* Large feature number in background */}
      <div
        style={{
          position: "absolute",
          top: -40,
          right: 60,
          fontSize: 320,
          fontWeight: 900,
          color: ACCENT,
          opacity: numberOpacity,
          fontFamily: "Inter, system-ui, sans-serif",
          lineHeight: 1,
          letterSpacing: "-15px",
          userSelect: "none",
        }}
      >
        {number}
      </div>

      {/* Browser mockup with screenshot */}
      <div
        style={{
          position: "absolute",
          top: 50,
          left: 80,
          right: 80,
          bottom: 200,
          opacity: frameOpacity,
          transform: `perspective(1200px) rotateX(${frameTiltX}deg) rotateY(${frameTiltY}deg) translateY(${frameTranslateY}px)`,
          transformOrigin: "center bottom",
        }}
      >
        <BrowserFrame>
          <div
            style={{
              width: "100%",
              height: "100%",
              overflow: "hidden",
              transform: `scale(${kenBurnsScale})`,
              transformOrigin: `${kb.originX} ${kb.originY}`,
            }}
          >
            <Img
              src={staticFile(image)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          </div>
        </BrowserFrame>
      </div>

      {/* Bottom text area */}
      <div
        style={{
          position: "absolute",
          bottom: 55,
          left: 80,
          right: 80,
        }}
      >
        {/* Accent line */}
        <div
          style={{
            width: lineWidth,
            height: 3,
            background: `linear-gradient(90deg, ${ACCENT}, ${ACCENT_LIGHT})`,
            borderRadius: 2,
            marginBottom: 16,
          }}
        />

        {/* Title with staggered words */}
        <StaggeredText
          text={title}
          startFrame={15}
          fontSize={44}
          color={TEXT}
        />

        {/* Subtitle */}
        <div
          style={{
            fontSize: 22,
            fontWeight: 400,
            color: MUTED,
            fontFamily: "Inter, system-ui, sans-serif",
            marginTop: 8,
            opacity: subtitleOpacity,
            transform: `translateY(${subtitleY}px)`,
            textShadow: "0 2px 10px rgba(0,0,0,0.6)",
          }}
        >
          {subtitle}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─── Intro scene ────────────────────────────────────────────────────────────
const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Logo entrance with bounce
  const logoScale = spring({
    frame,
    fps,
    from: 0,
    to: 1,
    config: { damping: 10, stiffness: 150, overshootClamping: false },
  });
  const logoRotate = spring({
    frame,
    fps,
    from: -15,
    to: 0,
    config: { damping: 12, stiffness: 100 },
  });

  // Glow pulses
  const glowScale = interpolate(
    frame,
    [0, 20, 50, 80, 105],
    [0, 1.2, 0.8, 1.0, 0.9],
    { extrapolateRight: "clamp" },
  );
  const glowOpacity = interpolate(
    frame,
    [0, 15, 50, 105],
    [0, 0.5, 0.35, 0.25],
    { extrapolateRight: "clamp" },
  );

  // Title: letter-by-letter reveal
  const titleText = "Proxysm";
  const titleLetters = titleText.split("").map((char, i) => {
    const delay = 12 + i * 3;
    const localFrame = Math.max(0, frame - delay);
    const charOpacity = spring({
      frame: localFrame,
      fps,
      config: { damping: 20, stiffness: 200, mass: 0.5 },
    });
    const charY = spring({
      frame: localFrame,
      fps,
      from: 30,
      to: 0,
      config: { damping: 15, stiffness: 180 },
    });
    const charScale = spring({
      frame: localFrame,
      fps,
      from: 0.5,
      to: 1,
      config: { damping: 12, stiffness: 160 },
    });

    return (
      <span
        key={i}
        style={{
          display: "inline-block",
          opacity: charOpacity,
          transform: `translateY(${charY}px) scale(${charScale})`,
        }}
      >
        {char}
      </span>
    );
  });

  // Tagline typewriter effect
  const tagline = "PROXY MANAGEMENT PLATFORM";
  const typewriterProgress = interpolate(frame, [35, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.linear,
  });
  const visibleChars = Math.floor(typewriterProgress * tagline.length);
  const taglineVisible = tagline.substring(0, visibleChars);
  const cursorVisible = frame > 35 && frame % 16 < 10;
  const taglineOpacity = interpolate(frame, [33, 38], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Decorative orbiting dots
  const orbit1Angle = (frame / 90) * Math.PI * 2;
  const orbit2Angle = (frame / 120) * Math.PI * 2 + Math.PI;

  // Horizontal lines
  const lineExtend = interpolate(frame, [50, 80], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{ background: BG }}>
      <AnimatedGrid seed="intro" opacity={0.2} />

      {/* Orbiting accent dots */}
      <div
        style={{
          position: "absolute",
          left: 960 + Math.cos(orbit1Angle) * 200,
          top: 540 + Math.sin(orbit1Angle) * 200,
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: ACCENT_LIGHT,
          opacity: 0.4,
          filter: "blur(1px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 960 + Math.cos(orbit2Angle) * 260,
          top: 540 + Math.sin(orbit2Angle) * 160,
          width: 4,
          height: 4,
          borderRadius: "50%",
          background: ACCENT,
          opacity: 0.3,
          filter: "blur(1px)",
        }}
      />

      {/* Glow sphere */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: 500,
          height: 500,
          marginLeft: -250,
          marginTop: -250,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${ACCENT_GLOW} 0%, transparent 70%)`,
          opacity: glowOpacity,
          transform: `scale(${glowScale})`,
          filter: "blur(40px)",
        }}
      />

      {/* Center content */}
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Logo */}
        <svg
          width={90}
          height={90}
          viewBox="0 0 24 24"
          style={{
            transform: `scale(${logoScale}) rotate(${logoRotate}deg)`,
            marginBottom: 28,
            filter: "drop-shadow(0 0 20px rgba(99,102,241,0.4))",
          }}
        >
          <defs>
            <linearGradient id="logoGrad" x1="0" y1="0" x2="24" y2="24">
              <stop offset="0%" stopColor={ACCENT_LIGHT} />
              <stop offset="100%" stopColor={ACCENT} />
            </linearGradient>
          </defs>
          <path d="M12 2L2 19h20L12 2z" fill="url(#logoGrad)" opacity="0.9" />
          <path d="M12 2L8 19h8L12 2z" fill="#A5B4FC" opacity="0.35" />
        </svg>

        {/* Title letters */}
        <div
          style={{
            fontSize: 80,
            fontWeight: 700,
            color: TEXT,
            fontFamily: "Inter, system-ui, sans-serif",
            letterSpacing: "-3px",
          }}
        >
          {titleLetters}
        </div>

        {/* Horizontal accent lines */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginTop: 16,
            marginBottom: 16,
          }}
        >
          <div
            style={{
              width: 60 * lineExtend,
              height: 2,
              background: `linear-gradient(90deg, transparent, ${ACCENT})`,
              borderRadius: 1,
            }}
          />
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: ACCENT,
              opacity: lineExtend,
              boxShadow: `0 0 10px ${ACCENT}`,
            }}
          />
          <div
            style={{
              width: 60 * lineExtend,
              height: 2,
              background: `linear-gradient(270deg, transparent, ${ACCENT})`,
              borderRadius: 1,
            }}
          />
        </div>

        {/* Tagline typewriter */}
        <div
          style={{
            fontSize: 22,
            fontWeight: 500,
            color: ACCENT,
            fontFamily: "SF Mono, Menlo, monospace",
            letterSpacing: "5px",
            opacity: taglineOpacity,
            minHeight: 30,
          }}
        >
          {taglineVisible}
          <span style={{ opacity: cursorVisible ? 1 : 0, color: ACCENT_LIGHT }}>
            |
          </span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ─── Outro scene ────────────────────────────────────────────────────────────
const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({
    frame,
    fps,
    from: 0.8,
    to: 1,
    config: { damping: 15, stiffness: 100 },
  });
  const contentOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });
  const badgeSlide = spring({
    frame: Math.max(0, frame - 15),
    fps,
    from: 20,
    to: 0,
    config: { damping: 20, stiffness: 150 },
  });
  const badgeOpacity = interpolate(frame, [15, 30], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Fade out at end
  const fadeOut = interpolate(frame, [OUTRO_DURATION - 20, OUTRO_DURATION], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const glowPulse = interpolate(
    frame,
    [0, 30, 60, 90],
    [0.2, 0.5, 0.3, 0.2],
    { extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ background: BG, opacity: fadeOut }}>
      <AnimatedGrid seed="outro" opacity={0.15} />

      {/* Glow */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: 600,
          height: 600,
          marginLeft: -300,
          marginTop: -300,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${ACCENT_GLOW} 0%, transparent 70%)`,
          opacity: glowPulse,
          filter: "blur(50px)",
        }}
      />

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity: contentOpacity,
        }}
      >
        {/* Logo */}
        <svg
          width={70}
          height={70}
          viewBox="0 0 24 24"
          style={{
            transform: `scale(${logoScale})`,
            marginBottom: 24,
            filter: "drop-shadow(0 0 15px rgba(99,102,241,0.3))",
          }}
        >
          <defs>
            <linearGradient id="outroGrad" x1="0" y1="0" x2="24" y2="24">
              <stop offset="0%" stopColor={ACCENT_LIGHT} />
              <stop offset="100%" stopColor={ACCENT} />
            </linearGradient>
          </defs>
          <path
            d="M12 2L2 19h20L12 2z"
            fill="url(#outroGrad)"
            opacity="0.9"
          />
          <path d="M12 2L8 19h8L12 2z" fill="#A5B4FC" opacity="0.35" />
        </svg>

        <div
          style={{
            fontSize: 56,
            fontWeight: 700,
            color: TEXT,
            fontFamily: "Inter, system-ui, sans-serif",
            letterSpacing: "-2px",
            marginBottom: 12,
          }}
        >
          Proxysm
        </div>

        {/* Badge */}
        <div
          style={{
            opacity: badgeOpacity,
            transform: `translateY(${badgeSlide}px)`,
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "rgba(99,102,241,0.12)",
            border: `1px solid rgba(99,102,241,0.25)`,
            borderRadius: 24,
            padding: "8px 20px",
            marginBottom: 20,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#28C840",
              boxShadow: "0 0 6px #28C840",
            }}
          />
          <span
            style={{
              fontSize: 16,
              fontWeight: 500,
              color: ACCENT_LIGHT,
              fontFamily: "Inter, system-ui, sans-serif",
              letterSpacing: "2px",
              textTransform: "uppercase",
            }}
          >
            Open Source
          </span>
        </div>

        <div
          style={{
            fontSize: 18,
            color: MUTED,
            fontFamily: "SF Mono, Menlo, monospace",
            opacity: badgeOpacity,
            letterSpacing: "1px",
          }}
        >
          github.com/pcko1/proxysm
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ─── Transition presets ─────────────────────────────────────────────────────
const transitions = [
  { presentation: wipe({ direction: "from-left" }), timing: linearTiming({ durationInFrames: TRANSITION_FRAMES, easing: Easing.inOut(Easing.cubic) }) },
  { presentation: slide({ direction: "from-right" }), timing: springTiming({ config: { damping: 200, stiffness: 100 } }) },
  { presentation: wipe({ direction: "from-bottom" }), timing: linearTiming({ durationInFrames: TRANSITION_FRAMES, easing: Easing.inOut(Easing.cubic) }) },
  { presentation: slide({ direction: "from-left" }), timing: springTiming({ config: { damping: 200, stiffness: 100 } }) },
  { presentation: fade(), timing: linearTiming({ durationInFrames: TRANSITION_FRAMES }) },
  { presentation: wipe({ direction: "from-right" }), timing: linearTiming({ durationInFrames: TRANSITION_FRAMES, easing: Easing.inOut(Easing.cubic) }) },
];

// ─── Main composition ───────────────────────────────────────────────────────
export const ProxysmShowcase: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: BG }}>
      <TransitionSeries>
        {/* Intro */}
        <TransitionSeries.Sequence durationInFrames={INTRO_DURATION}>
          <IntroScene />
        </TransitionSeries.Sequence>

        {/* Feature slides with transitions */}
        {SLIDES.map((slide, i) => (
          <React.Fragment key={i}>
            <TransitionSeries.Transition
              presentation={transitions[i].presentation}
              timing={transitions[i].timing}
            />
            <TransitionSeries.Sequence durationInFrames={SLIDE_DURATION}>
              <FeatureSlide
                image={slide.image}
                title={slide.title}
                subtitle={slide.subtitle}
                number={slide.number}
                kb={slide.kb}
              />
            </TransitionSeries.Sequence>
          </React.Fragment>
        ))}

        {/* Outro transition */}
        <TransitionSeries.Transition
          presentation={transitions[5].presentation}
          timing={transitions[5].timing}
        />
        <TransitionSeries.Sequence durationInFrames={OUTRO_DURATION}>
          <OutroScene />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};
