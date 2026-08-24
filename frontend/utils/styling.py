"""Custom CSS injected once per page load to move the UI away from default
Streamlit styling — gradient hero banners, card panels, chips, a stepper,
and a consistent accent color used throughout."""
import streamlit as st

PRIMARY = "#6C5CE7"
PRIMARY_DARK = "#4834D4"
ACCENT = "#00CEC9"
SUCCESS = "#00B894"
WARNING = "#FDCB6E"
DANGER = "#FF6B6B"
INK = "#1B1B2F"

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
}}
h1, h2, h3, h4 {{
    font-family: 'Sora', sans-serif !important;
    letter-spacing: -0.02em;
}}

.stApp {{
    background: radial-gradient(circle at 10% 0%, #1B1B2F 0%, #0F0F1A 55%, #0A0A12 100%);
    color: #F1F1F6;
}}

section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #14142B 0%, #0F0F1A 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}}

/* Hero banner */
.hero-banner {{
    background: linear-gradient(120deg, {PRIMARY} 0%, {PRIMARY_DARK} 55%, {ACCENT} 130%);
    padding: 2.2rem 2.5rem;
    border-radius: 20px;
    margin-bottom: 1.6rem;
    box-shadow: 0 10px 40px rgba(108, 92, 231, 0.35);
}}
.hero-banner h1 {{
    color: white;
    margin: 0 0 0.4rem 0;
    font-size: 2.1rem;
}}
.hero-banner p {{
    color: rgba(255,255,255,0.9);
    margin: 0;
    font-size: 1.02rem;
}}

/* Stepper */
.stepper {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 1.8rem;
    gap: 0.5rem;
}}
.step {{
    flex: 1;
    text-align: center;
    padding: 0.65rem 0.4rem;
    border-radius: 12px;
    font-weight: 600;
    font-size: 0.82rem;
    background: rgba(255,255,255,0.04);
    color: rgba(255,255,255,0.45);
    border: 1px solid rgba(255,255,255,0.08);
}}
.step.active {{
    background: linear-gradient(120deg, {PRIMARY}, {ACCENT});
    color: white;
    border: none;
    box-shadow: 0 6px 18px rgba(108,92,231,0.4);
}}
.step.done {{
    background: rgba(0, 184, 148, 0.15);
    color: {SUCCESS};
    border: 1px solid rgba(0,184,148,0.35);
}}

/* Card panel */
.card {{
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.1rem;
}}
.card h4 {{
    margin-top: 0;
    color: {ACCENT};
}}

/* Chips */
.chip {{
    display: inline-block;
    padding: 0.28rem 0.75rem;
    margin: 0.18rem 0.28rem 0.18rem 0;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 500;
    background: rgba(108,92,231,0.18);
    border: 1px solid rgba(108,92,231,0.4);
    color: #D6D0FF;
}}
.chip.strong {{ background: rgba(0,184,148,0.18); border-color: rgba(0,184,148,0.4); color: #9BF6DF; }}
.chip.partial {{ background: rgba(253,203,110,0.18); border-color: rgba(253,203,110,0.4); color: #FFE3A3; }}
.chip.missing {{ background: rgba(255,107,107,0.18); border-color: rgba(255,107,107,0.4); color: #FFB3B3; }}

/* Question bubble in interview screen */
.ai-question {{
    background: linear-gradient(120deg, rgba(108,92,231,0.22), rgba(0,206,201,0.14));
    border: 1px solid rgba(108,92,231,0.4);
    border-radius: 18px 18px 18px 4px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
    font-size: 1.05rem;
    line-height: 1.5;
}}
.level-badge {{
    display: inline-block;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.6rem;
}}
.level-screening {{ background: rgba(0,206,201,0.2); color: #7FFFF5; }}
.level-competency {{ background: rgba(253,203,110,0.2); color: {WARNING}; }}
.level-deep_dive {{ background: rgba(255,107,107,0.2); color: {DANGER}; }}

.readiness-banner {{
    text-align: center;
    padding: 1.6rem;
    border-radius: 18px;
    font-size: 1.4rem;
    font-weight: 800;
    margin-bottom: 1.2rem;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
}}

div.stButton > button {{
    background: linear-gradient(120deg, {PRIMARY}, {PRIMARY_DARK});
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.55rem 1.4rem;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(108,92,231,0.35);
}}
div.stButton > button:hover {{
    box-shadow: 0 6px 20px rgba(108,92,231,0.55);
    transform: translateY(-1px);
}}

hr {{ border-color: rgba(255,255,255,0.08); }}
</style>
"""


def inject_custom_css() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""<div class="hero-banner"><h1>{title}</h1><p>{subtitle}</p></div>""",
        unsafe_allow_html=True,
    )


def stepper(current_stage: str) -> None:
    stages = [
        ("dashboard", "1 · Upload"),
        ("role_analysis", "2 · Role Analysis"),
        ("candidate_analysis", "3 · Candidate Fit"),
        ("interview", "4 · AI Interview"),
        ("results", "5 · Results"),
    ]
    order = [s[0] for s in stages]
    current_idx = order.index(current_stage) if current_stage in order else 0
    html = ['<div class="stepper">']
    for i, (key, label) in enumerate(stages):
        cls = "step"
        if i < current_idx:
            cls += " done"
        elif i == current_idx:
            cls += " active"
        html.append(f'<div class="{cls}">{label}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def chips(items: list[str], variant: str = "") -> str:
    cls = f"chip {variant}".strip()
    return "".join(f'<span class="{cls}">{item}</span>' for item in items) or "<i>None listed</i>"
