import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  spring,
  useVideoConfig,
} from "remotion";

const SLIDES = [
  {
    image: "screenshots/01-proxies.png",
    title: "Proxy Management",
    subtitle: "Import, monitor & manage thousands of proxies with source tracking",
  },
  {
    image: "screenshots/02-dashboard.png",
    title: "Real-Time Dashboard",
    subtitle: "Health rings, provider overview, pool utilization at a glance",
  },
  {
    image: "screenshots/03-import-modal.png",
    title: "Flexible Import",
    subtitle: "Paste, upload files, or fetch from URLs with auto-polling",
  },
  {
    image: "screenshots/04-pools.png",
    title: "Pool Rotation",
    subtitle: "Round-robin & random strategies with health-aware routing",
  },
  {
    image: "screenshots/05-api-docs.png",
    title: "Full REST API",
    subtitle: "Interactive API docs with Redocly — every feature accessible via API",
  },
];

const SLIDE_DURATION = 75; // frames per slide (2.5s at 30fps)
const TRANSITION = 15; // transition frames

const Slide: React.FC<{
  image: string;
  title: string;
  subtitle: string;
}> = ({ image, title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scaleSpring = spring({ frame, fps, from: 1.05, to: 1, durationInFrames: 30 });
  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const textSlide = spring({ frame, fps, from: 40, to: 0, durationInFrames: 20 });
  const subtitleFade = interpolate(frame, [10, 22], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: "#07070B" }}>
      {/* Screenshot */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          opacity: fadeIn,
          transform: `scale(${scaleSpring})`,
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
        {/* Dark gradient overlay at bottom */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: "35%",
            background: "linear-gradient(transparent, rgba(7,7,11,0.95))",
          }}
        />
      </div>

      {/* Title text */}
      <div
        style={{
          position: "absolute",
          bottom: 80,
          left: 80,
          transform: `translateY(${textSlide}px)`,
          opacity: fadeIn,
        }}
      >
        <div
          style={{
            fontSize: 48,
            fontWeight: 700,
            color: "#EDEDF0",
            fontFamily: "Inter, system-ui, sans-serif",
            letterSpacing: "-1px",
            textShadow: "0 2px 20px rgba(0,0,0,0.8)",
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: 24,
            fontWeight: 400,
            color: "#9898A6",
            fontFamily: "Inter, system-ui, sans-serif",
            marginTop: 8,
            opacity: subtitleFade,
            textShadow: "0 2px 10px rgba(0,0,0,0.8)",
          }}
        >
          {subtitle}
        </div>
      </div>

      {/* Accent line */}
      <div
        style={{
          position: "absolute",
          bottom: 70,
          left: 80,
          width: interpolate(frame, [0, 20], [0, 60], { extrapolateRight: "clamp" }),
          height: 3,
          background: "#6366F1",
          borderRadius: 2,
        }}
      />
    </AbsoluteFill>
  );
};

const IntroSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({ frame, fps, from: 0, to: 1, durationInFrames: 20 });
  const titleFade = interpolate(frame, [10, 25], [0, 1], { extrapolateRight: "clamp" });
  const titleSlide = spring({ frame: Math.max(0, frame - 10), fps, from: 30, to: 0, durationInFrames: 20 });
  const subtitleFade = interpolate(frame, [20, 35], [0, 1], { extrapolateRight: "clamp" });
  const glowPulse = interpolate(frame, [0, 30, 60], [0, 0.4, 0.2], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: "#07070B",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Glow */}
      <div
        style={{
          position: "absolute",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,102,241,0.3) 0%, transparent 70%)",
          opacity: glowPulse,
          filter: "blur(60px)",
        }}
      />

      {/* Logo triangle */}
      <svg
        width={80}
        height={80}
        viewBox="0 0 24 24"
        style={{ transform: `scale(${logoScale})`, marginBottom: 24 }}
      >
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="24" y2="24">
            <stop offset="0%" stopColor="#818CF8" />
            <stop offset="100%" stopColor="#6366F1" />
          </linearGradient>
        </defs>
        <path d="M12 2L2 19h20L12 2z" fill="url(#g)" opacity="0.9" />
        <path d="M12 2L8 19h8L12 2z" fill="#A5B4FC" opacity="0.4" />
      </svg>

      <div
        style={{
          fontSize: 72,
          fontWeight: 700,
          color: "#EDEDF0",
          fontFamily: "Inter, system-ui, sans-serif",
          letterSpacing: "-2px",
          opacity: titleFade,
          transform: `translateY(${titleSlide}px)`,
        }}
      >
        Proxysm
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 400,
          color: "#6366F1",
          fontFamily: "Inter, system-ui, sans-serif",
          marginTop: 12,
          opacity: subtitleFade,
          letterSpacing: "4px",
          textTransform: "uppercase",
        }}
      >
        Proxy Management Platform
      </div>
    </AbsoluteFill>
  );
};

export const ProxysmShowcase: React.FC = () => {
  const INTRO_DURATION = 75;

  return (
    <AbsoluteFill style={{ background: "#07070B" }}>
      {/* Intro */}
      <Sequence from={0} durationInFrames={INTRO_DURATION}>
        <IntroSlide />
      </Sequence>

      {/* Feature slides */}
      {SLIDES.map((slide, i) => (
        <Sequence
          key={i}
          from={INTRO_DURATION + i * SLIDE_DURATION}
          durationInFrames={SLIDE_DURATION}
        >
          <Slide image={slide.image} title={slide.title} subtitle={slide.subtitle} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
