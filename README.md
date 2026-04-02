# PeakFuel

PeakFuel is a mobile-friendly Streamlit app for AI-assisted fitness tracking. It supports natural-language logging for workouts, hikes, and food, with voice upload + transcription, structured parsing, local persistence, analytics dashboards, streaks, and trophies.

## Features

- **Dashboard** with premium metric cards and trend charts.
- **Voice Log**: upload audio, transcribe with OpenAI (if API key configured), edit transcript, then parse.
- **Manual Log**: type natural-language entries and parse into structured forms before saving.
- **SQLite persistence** with normalized tables:
  - workouts / workout_exercises
  - hikes
  - foods / food_items
  - trophies
  - profile
- **History pages** for workouts, hikes, and meals with filtering + delete actions.
- **Progress & Stats** with interactive Plotly charts and advanced metrics.
- **Trophy system** with unlock logic, progress bars, and earned dates.
- **Demo seed data** (20 workouts, 12 hikes, 30 food logs).

## Project Structure

```text
Peakfuel/
├── app.py
├── db.py
├── ai_parser.py
├── utils.py
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

1. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Add your OpenAI API key to `.env`.

4. **Run the app**
   ```bash
   streamlit run app.py
   ```

## Notes

- Without `OPENAI_API_KEY`, parsing and transcription fallback gracefully to heuristic parsing or manual transcript entry.
- Database file is created locally as `peakfuel.db` in the project root.
- Demo data seeds automatically on first launch when database is empty.
