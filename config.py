"""
config.py
Everything you can personalize lives here. No AI-style dash punctuation in the
values on the right panel. Decorative separators are added by the renderer.

Uptime rule:
  - set BIRTH_DATE to show your age like the reference profile does
  - leave it None to show time since CODING_SINCE instead
"""

CONFIG = {
    # terminal prompt: user@host
    "user": "said",
    "host": "mit",

    # left of the '@' identity block (neofetch style key: value)
    "identity": [
        ("OS", "macOS Sequoia, Linux, iOS"),
        ("Host", "MIT"),
        ("Role", "Full Stack Developer and Researcher"),
        ("Focus", "AI Tooling, Automation, Web Platforms"),
        ("IDE", "Cursor, VS Code, Claude Code"),
        ("Typing", "100 WPM average"),
    ],

    "languages": [
        ("Programming", "TypeScript, Python, JavaScript, SQL"),
        ("Frameworks", "React, FastAPI, Vite, Tailwind"),
        ("Cloud", "Supabase, Cloudflare, Docker"),
        ("Spoken", "English, Hebrew, Arabic"),
    ],

    "hobbies": [
        ("Building", "Crowdfunding, Research Platforms"),
        ("Research", "Peptide Prediction, Data Pipelines"),
    ],

    "contact": [
        ("GitHub", "az-said"),
        ("LinkedIn", "in/said-azaizah"),
    ],

    # dynamic fields
    "birth_date": None,          # e.g. "1999-04-12" to show your real age
    "coding_since": "2019-01-01",
    "timezone": "Asia/Jerusalem",

    # look and feel
    "theme": "cyberpunk",        # cyberpunk neon locked in
    "portrait_style": "pixel",   # pixel | ascii | braille  (hero output)
    "portrait_mode": "duotone",  # truecolor | neon | duotone
    "photo": "assets/photo.jpg",

    "title_tagline": "builder-operator // full-stack // researcher",
}
