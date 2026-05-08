"""Streamlit CSS."""

from __future__ import annotations


CSS = """
<style>
:root {
  --amanah-green: #0f8f5f;
  --amanah-soft: #eef8f3;
  --amanah-border: #e7e7e7;
  --amanah-ink: #111111;
}
.main .block-container { max-width: 1080px; padding-top: 2rem; }
h1, h2, h3 { letter-spacing: 0; color: var(--amanah-ink); }
.amanah-tagline { color: #5f6662; margin-top: -0.8rem; margin-bottom: 1.4rem; }
.verdict-card {
  border: 1px solid var(--amanah-border);
  border-radius: 8px;
  padding: 1.35rem;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(0,0,0,0.04);
}
.verdict-badge {
  display: inline-block;
  padding: 0.42rem 0.8rem;
  border-radius: 999px;
  color: #ffffff;
  font-weight: 800;
  letter-spacing: 0.04em;
  font-size: 0.9rem;
}
.badge-pass { background: #0f8f5f; }
.badge-fail { background: #111111; }
.badge-review { background: #b7791f; }
.rule-card {
  border: 1px solid var(--amanah-border);
  border-radius: 8px;
  padding: 1rem;
  background: #ffffff;
  min-height: 300px;
}
.blocker-card {
  border: 1px solid var(--amanah-border);
  border-left: 4px solid var(--amanah-green);
  border-radius: 8px;
  padding: 1rem;
  background: var(--amanah-soft);
  margin: 1rem 0;
}
.rule-title { font-weight: 800; margin-bottom: 0.35rem; }
.muted { color: #666; font-size: 0.92rem; }
.small-label { color: #666; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
.metric-line { margin: 0.35rem 0; }
</style>
"""
