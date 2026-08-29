"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

const AGENTS = [
  {
    icon: "⚡",
    name: "Command Agent",
    role: "Executive Brain",
    desc: "Interprets your goals and delegates tasks across your entire AI workforce — instantly.",
    route: "/command",
  },
  {
    icon: "🔁",
    name: "Workflow Agent",
    role: "Process Architect",
    desc: "Designs, optimizes, and runs automated workflows end-to-end without human bottlenecks.",
    route: "/workflows",
  },
  {
    icon: "🔍",
    name: "Audit Agent",
    role: "Quality Guardian",
    desc: "Monitors every decision, flags anomalies, and ensures operations stay on-track.",
    route: "/audit",
  },
  {
    icon: "🤝",
    name: "Ops Agent",
    role: "Execution Engine",
    desc: "Handles day-to-day operations — emails, data, reports, scheduling — autonomously.",
    route: "/agents",
  },
];

const STEPS = [
  { num: "01", title: "Tell us the outcome", desc: "No need for step-by-step instructions. Just describe what you want achieved — revenue, growth, efficiency." },
  { num: "02", title: "Agents get to work", desc: "MAICOS assigns the right agents automatically, builds a plan, and begins executing across your business." },
  { num: "03", title: "Verify & refine", desc: "Review every action in real-time. Approve, redirect, or let agents run fully autonomous." },
  { num: "04", title: "Scale infinitely", desc: "Add more goals, more agents, more routes. Your AI company OS grows with your ambition." },
];

const USE_CASES = [
  { emoji: "🏢", title: "Startups", desc: "Replace an entire ops team with 10 specialized agents from day one." },
  { emoji: "📊", title: "Scale-ups", desc: "Run parallel workflows across sales, marketing, and finance simultaneously." },
  { emoji: "🏭", title: "Enterprises", desc: "Automate compliance, reporting, and cross-department coordination at scale." },
  { emoji: "🛒", title: "E-commerce", desc: "Manage inventory, customer ops, and growth campaigns — all on autopilot." },
  { emoji: "💼", title: "Agencies", desc: "Deliver client work 5x faster with AI agents handling research, writing, and execution." },
  { emoji: "🔬", title: "SaaS", desc: "Automate onboarding, support, and analytics pipelines without engineering bandwidth." },
];

const TESTIMONIALS = [
  { name: "Priya Sharma", role: "CEO, NovaBuild", text: "MAICOS replaced three full-time hires in our ops team. It just runs — and it runs perfectly.", stars: 5 },
  { name: "Alex Chen", role: "Founder, Loopflow", text: "I told it to grow MRR by 20%. Two weeks later, we were at 23%. I'm still processing that.", stars: 5 },
  { name: "Raya Okafor", role: "COO, Meridian Labs", text: "The audit agent alone is worth it. It caught a $40k billing error we'd have missed for months.", stars: 5 },
];

export default function MAICOSLanding() {
  const [activeTab, setActiveTab] = useState(0);
  const [testimonyIdx, setTestimonyIdx] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setTestimonyIdx((i) => (i + 1) % TESTIMONIALS.length), 6000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="maicos-landing">
      {/* ── NAV ── */}
      <nav className={`m-nav ${scrolled ? "m-nav--scrolled" : ""}`}>
        <div className="m-nav__inner">
          <Link href="/" className="m-nav__logo">MAICOS</Link>
          <div className={`m-nav__links ${menuOpen ? "open" : ""}`}>
            <Link href="#agents" onClick={() => setMenuOpen(false)}>Agents</Link>
            <Link href="#how" onClick={() => setMenuOpen(false)}>How it Works</Link>
            <Link href="#usecases" onClick={() => setMenuOpen(false)}>Use Cases</Link>
            <Link href="#testimonials" onClick={() => setMenuOpen(false)}>Reviews</Link>
            <Link href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</Link>
          </div>
          <div className="m-nav__actions">
            <Link href="/login" className="m-btn m-btn--ghost">Sign In</Link>
            <Link href="/command" className="m-btn m-btn--primary">Open Command Center</Link>
          </div>
          <button className="m-nav__burger" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
            <span /><span /><span />
          </button>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="m-hero" ref={heroRef}>
        <div className="m-hero__video-wrap">
          <video autoPlay muted loop playsInline>
            <source src="https://api.getlayers.ai/storage/v1/object/public/public/assets/loopstack-f8c64439bf/flower.mp4" type="video/mp4" />
          </video>
          <div className="m-hero__overlay" />
        </div>
        <div className="m-hero__content">
          <div className="m-hero__badge">
            <span className="m-dot" /> 10 Specialized Agents · Live
          </div>
          <h1 className="m-hero__title">
            Tell us the outcome.<br />
            <em>We run the company for you.</em>
          </h1>
          <p className="m-hero__sub">
            Multi-agent AI company OS — built to automate, delegate, and execute across every function of your business.
          </p>
          <div className="m-hero__ctas">
            <Link href="/command" className="m-btn m-btn--hero-primary">
              Open Command Center
              <span className="m-dot" />
            </Link>
            <Link href="#how" className="m-btn m-btn--hero-ghost">See How It Works</Link>
          </div>
          <div className="m-hero__stats">
            <div className="m-stat"><span>10</span>Agents</div>
            <div className="m-stat-div" />
            <div className="m-stat"><span>27</span>Verified Routes</div>
            <div className="m-stat-div" />
            <div className="m-stat"><span>∞</span>Scale</div>
          </div>
        </div>
        <div className="m-hero__scroll">
          <span>Scroll to explore</span>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3v10M4 9l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </section>

      {/* ── PHILOSOPHY ── */}
      <section className="m-section m-philosophy">
        <div className="m-container m-container--narrow text-center">
          <p className="m-overline">Our Belief</p>
          <h2 className="m-h2">Built for the age of autonomous business</h2>
          <p className="m-body-lg">
            Every company deserves an AI workforce that understands intent, not just instructions. MAICOS doesn't wait for prompts — it thinks, delegates, executes, and verifies. Like a Chief of Staff that never sleeps.
          </p>
          <div className="m-divider-leaf">
            <div className="m-divider-line" />
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2c0 0-7 4-7 9a7 7 0 0014 0c0-5-7-9-7-9z" fill="currentColor" opacity=".3"/><path d="M10 2v16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            <div className="m-divider-line" />
          </div>
        </div>
      </section>

      {/* ── AGENTS ── */}
      <section className="m-section" id="agents">
        <div className="m-container">
          <div className="m-section-header">
            <p className="m-overline">Your AI Workforce</p>
            <h2 className="m-h2">Meet Your Agents</h2>
            <p className="m-body">Specialized AI agents, each an expert in their domain. All working in sync.</p>
          </div>
          <div className="m-agents-grid">
            {AGENTS.map((a) => (
              <Link href={a.route} key={a.name} className="m-agent-card">
                <div className="m-agent-card__icon">{a.icon}</div>
                <div className="m-agent-card__body">
                  <p className="m-agent-card__role">{a.role}</p>
                  <h3 className="m-agent-card__name">{a.name}</h3>
                  <p className="m-agent-card__desc">{a.desc}</p>
                </div>
                <div className="m-agent-card__cta">
                  Explore Agent
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7h10M8 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="m-section m-section--alt" id="how">
        <div className="m-container">
          <div className="m-section-header">
            <p className="m-overline">The Process</p>
            <h2 className="m-h2">How MAICOS Works</h2>
            <p className="m-body">From goal to execution in four steps. No technical setup. No micromanaging.</p>
          </div>
          <div className="m-steps">
            {STEPS.map((s) => (
              <div key={s.num} className="m-step">
                <div className="m-step__num">{s.num}</div>
                <div className="m-step__body">
                  <h3 className="m-step__title">{s.title}</h3>
                  <p className="m-step__desc">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── USE CASES ── */}
      <section className="m-section" id="usecases">
        <div className="m-container">
          <div className="m-section-header">
            <p className="m-overline">Built For Everyone</p>
            <h2 className="m-h2">What kind of company are you?</h2>
            <p className="m-body">MAICOS adapts to your industry, your team size, and your ambition.</p>
          </div>
          <div className="m-usecases-grid">
            {USE_CASES.map((u) => (
              <div key={u.title} className="m-usecase-card">
                <span className="m-usecase-card__emoji">{u.emoji}</span>
                <h3 className="m-usecase-card__title">{u.title}</h3>
                <p className="m-usecase-card__desc">{u.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS ── */}
      <section className="m-section m-section--alt" id="testimonials">
        <div className="m-container m-container--narrow">
          <div className="m-section-header">
            <p className="m-overline">Social Proof</p>
            <h2 className="m-h2">What founders are saying</h2>
          </div>
          <div className="m-testimonial">
            <div className="m-testimonial__quote">&ldquo;</div>
            <p className="m-testimonial__text">{TESTIMONIALS[testimonyIdx].text}</p>
            <div className="m-testimonial__stars">{"★".repeat(TESTIMONIALS[testimonyIdx].stars)}</div>
            <div className="m-testimonial__author">
              <strong>{TESTIMONIALS[testimonyIdx].name}</strong>
              <span>{TESTIMONIALS[testimonyIdx].role}</span>
            </div>
            <div className="m-testimonial__dots">
              {TESTIMONIALS.map((_, i) => (
                <button key={i} className={`m-dot-btn ${i === testimonyIdx ? "active" : ""}`} onClick={() => setTestimonyIdx(i)} aria-label={`Review ${i+1}`} />
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section className="m-section" id="pricing">
        <div className="m-container">
          <div className="m-section-header">
            <p className="m-overline">Simple Pricing</p>
            <h2 className="m-h2">Start running your AI company</h2>
          </div>
          <div className="m-pricing-grid">
            {[
              { plan: "Starter", price: "$0", period: "forever", desc: "For founders exploring AI-first ops.", features: ["3 Active Agents", "5 Workflows/month", "Command Center access", "Basic Audit logs"], cta: "Get Started", highlight: false },
              { plan: "Growth", price: "$49", period: "per month", desc: "For teams ready to delegate everything.", features: ["10 Active Agents", "Unlimited Workflows", "All 27 routes unlocked", "Priority Audit + alerts", "Supabase Auth included"], cta: "Start Free Trial", highlight: true },
              { plan: "Enterprise", price: "Custom", period: "bespoke", desc: "For companies that run on MAICOS.", features: ["Unlimited Agents", "Custom integrations", "Dedicated support", "SLA & compliance", "On-premise option"], cta: "Contact Us", highlight: false },
            ].map((p) => (
              <div key={p.plan} className={`m-plan-card ${p.highlight ? "m-plan-card--highlight" : ""}`}>
                {p.highlight && <div className="m-plan-card__badge">Most Popular</div>}
                <div className="m-plan-card__top">
                  <h3 className="m-plan-card__name">{p.plan}</h3>
                  <div className="m-plan-card__price">
                    <span className="m-plan-card__amount">{p.price}</span>
                    <span className="m-plan-card__period">/{p.period}</span>
                  </div>
                  <p className="m-plan-card__desc">{p.desc}</p>
                </div>
                <ul className="m-plan-card__features">
                  {p.features.map((f) => (
                    <li key={f}>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7l3.5 3.5L12 3" stroke="#39ff14" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      {f}
                    </li>
                  ))}
                </ul>
                <Link href="/command" className={`m-btn ${p.highlight ? "m-btn--primary" : "m-btn--ghost"} m-btn--full`}>{p.cta}</Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA BANNER ── */}
      <section className="m-cta-banner">
        <div className="m-container m-container--narrow text-center">
          <h2 className="m-cta-banner__title">Ready to delegate everything?</h2>
          <p className="m-cta-banner__sub">Join the founders who let MAICOS run their company while they focus on what matters.</p>
          <Link href="/command" className="m-btn m-btn--primary m-btn--lg">
            Open Command Center
            <span className="m-dot" />
          </Link>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="m-footer">
        <div className="m-container">
          <div className="m-footer__top">
            <div className="m-footer__brand">
              <h2 className="m-footer__logo">MAICOS</h2>
              <p className="m-footer__tagline">Multi-Agent AI Company OS. Built for the ambitious.</p>
              <div className="m-footer__socials">
                {["GitHub","X","LinkedIn"].map(s => <a key={s} href="#" className="m-social" aria-label={s}>{s[0]}</a>)}
              </div>
            </div>
            <div className="m-footer__links-group">
              <div className="m-footer__col">
                <p className="m-footer__col-title">Product</p>
                <Link href="/command">Command</Link>
                <Link href="/workflows">Workflows</Link>
                <Link href="/agents">Agents</Link>
                <Link href="/audit">Audit</Link>
              </div>
              <div className="m-footer__col">
                <p className="m-footer__col-title">Company</p>
                <Link href="#">About</Link>
                <Link href="#">Blog</Link>
                <Link href="#">Careers</Link>
                <Link href="#">Contact</Link>
              </div>
              <div className="m-footer__col">
                <p className="m-footer__col-title">Legal</p>
                <Link href="#">Privacy</Link>
                <Link href="#">Terms</Link>
                <Link href="#">Security</Link>
              </div>
            </div>
          </div>
          <div className="m-footer__bottom">
            <div className="m-footer__wordmark">MAICOS</div>
            <p className="m-footer__copy">© 2026 MAICOS. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
