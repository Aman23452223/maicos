"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";

const ASSET_BASE =
  "https://api.getlayers.ai/storage/v1/object/public/public/assets/loopstack-f8c64439bf";

export default function HeroLanding() {
  const logoTextRef = useRef<HTMLHeadingElement | null>(null);
  const heroTitleRef = useRef<HTMLHeadingElement | null>(null);
  const glassCardRef = useRef<HTMLDivElement | null>(null);
  const cursorRingRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    /* ---- wordmark letter reveal ---- */
    const logoText = logoTextRef.current;
    if (logoText && !logoText.dataset.animated) {
      logoText.dataset.animated = "true";
      const text = logoText.textContent ?? "";
      logoText.innerHTML = "";
      [...text].forEach((char, index) => {
        const wrapper = document.createElement("span");
        wrapper.className = "letter-wrapper";
        const inner = document.createElement("span");
        inner.className = "letter-inner";
        inner.textContent = char === " " ? " " : char;
        inner.style.animationDelay = `${index * 0.09}s`;
        wrapper.appendChild(inner);
        logoText.appendChild(wrapper);
      });
    }

    /* ---- hero headline word reveal ---- */
    const heroTitle = heroTitleRef.current;
    if (heroTitle && !heroTitle.dataset.animated) {
      heroTitle.dataset.animated = "true";
      const text = heroTitle.innerHTML;
      const parts = text.split(/(\s+|<br\s*\/?>)/i);
      heroTitle.innerHTML = "";
      let wordIndex = 0;
      parts.forEach((part) => {
        if (part.trim() === "") {
          heroTitle.appendChild(document.createTextNode(" "));
        } else if (part.toLowerCase().startsWith("<br")) {
          heroTitle.appendChild(document.createElement("br"));
        } else {
          const wrapper = document.createElement("span");
          wrapper.className = "word-wrapper";
          const inner = document.createElement("span");
          inner.className = "word-inner";
          inner.textContent = part;
          inner.style.animationDelay = `${wordIndex * 0.1}s`;
          wordIndex++;
          wrapper.appendChild(inner);
          heroTitle.appendChild(wrapper);
        }
      });
    }

    /* ---- custom cursor + LERP pill ---- */
    const glassCard = glassCardRef.current;
    const cursorRing = cursorRingRef.current;
    if (!glassCard || !cursorRing) return;

    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let cardX = mouseX;
    let cardY = mouseY;
    let ringX = mouseX;
    let ringY = mouseY;
    let isFirstMove = true;
    let scale = 0;
    let targetScale = 0;
    let isHoveringBtn = false;

    const onMove = (e: MouseEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      if (isFirstMove) {
        cardX = mouseX;
        cardY = mouseY;
        ringX = mouseX;
        ringY = mouseY;
        isFirstMove = false;
        glassCard.classList.add("active");
        cursorRing.classList.add("active");
      }
      if (!isHoveringBtn) targetScale = 1;
    };
    const onLeave = () => {
      targetScale = 0;
    };
    const onEnter = () => {
      if (!isHoveringBtn) targetScale = 1;
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseenter", onEnter);

    const heroBtn = document.querySelector<HTMLElement>(".hero-btn");
    const onBtnEnter = () => {
      isHoveringBtn = true;
      targetScale = 0;
      cursorRing.classList.add("expanded");
    };
    const onBtnLeave = () => {
      isHoveringBtn = false;
      targetScale = 1;
      cursorRing.classList.remove("expanded");
    };
    if (heroBtn) {
      heroBtn.addEventListener("mouseenter", onBtnEnter);
      heroBtn.addEventListener("mouseleave", onBtnLeave);
    }

    let raf = 0;
    const tick = () => {
      cardX += (mouseX - cardX) * 0.08;
      cardY += (mouseY - cardY) * 0.08;
      ringX = mouseX;
      ringY = mouseY;
      scale += (targetScale - scale) * 0.15;
      const ringScale = cursorRing.classList.contains("expanded")
        ? 1.6 * scale
        : scale;
      glassCard.style.transform = `translate3d(${cardX}px, ${cardY}px, 0) translate(-50%, -50%) scale(${scale})`;
      cursorRing.style.transform = `translate3d(${ringX}px, ${ringY}px, 0) translate(-50%, -50%) scale(${ringScale})`;
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseenter", onEnter);
      if (heroBtn) {
        heroBtn.removeEventListener("mouseenter", onBtnEnter);
        heroBtn.removeEventListener("mouseleave", onBtnLeave);
      }
    };
  }, []);

  return (
    <div className="hero-root">
      <img
        src={`${ASSET_BASE}/black_gradient.svg`}
        alt="Top gradient"
        id="top-gradient"
      />

      <main className="hero-content">
        <h1 className="hero-title" ref={heroTitleRef}>
          Tell us the outcome. <br /> We run the company for you.
        </h1>
        <Link href="/command" className="hero-btn" aria-label="Open the command center">
          <span className="btn-text">Open Command Center</span>
          <span className="blinking-dot" aria-hidden="true" />
        </Link>
        <p className="hero-sub">
          Multi-agent AI company OS · 10 specialized agents · 27 verified routes
        </p>
      </main>

      <footer className="footer-container">
        <div className="footer-top">
          <h2 className="footer-title">Stay in the loop</h2>
          <h2 className="footer-title quote">Plan. Delegate. Verify.</h2>
        </div>

        <hr className="footer-divider" />

        <div className="footer-bottom">
          <div className="footer-socials">
            <a href="#" aria-label="GitHub" className="social-icon">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
              </svg>
            </a>
            <a href="#" aria-label="X" className="social-icon">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 4l11.733 16h4.267l-11.733 -16z" />
                <path d="M4 20l6.768 -6.768m2.46 -2.46l6.772 -6.772" />
              </svg>
            </a>
            <a href="#" aria-label="LinkedIn" className="social-icon">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
                <rect x="2" y="9" width="4" height="12" />
                <circle cx="4" cy="4" r="2" />
              </svg>
            </a>
          </div>

          <nav className="footer-links">
            <Link href="/command" className="footer-link">
              Command
            </Link>
            <Link href="/workflows" className="footer-link">
              Workflows
            </Link>
            <Link href="/agents" className="footer-link">
              Agents
            </Link>
            <Link href="/audit" className="footer-link">
              Audit
            </Link>
          </nav>

          <div className="footer-copyright">© 2026 MAICOS</div>
        </div>
      </footer>

      <div className="footer-logo-wrap">
        <h2 className="footer-logo-text" ref={logoTextRef}>
          MAICOS
        </h2>
      </div>

      <div className="video-container">
        <video autoPlay muted loop playsInline id="bg-video">
          <source src={`${ASSET_BASE}/flower.mp4`} type="video/mp4" />
        </video>
      </div>

      <div id="cursor-ring" className="cursor-ring-outline" ref={cursorRingRef} />
      <div id="glass-card" className="glass-cursor-card" ref={glassCardRef}>
        <span className="cursor-card-text">
          <span className="text-white">Run</span> Workflow!
        </span>
      </div>
    </div>
  );
}
