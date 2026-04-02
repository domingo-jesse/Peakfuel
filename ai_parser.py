import json
import os
import re
from datetime import date
from typing import Any


def _openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=api_key)
    except Exception:
        return None


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}
    return {}


def parse_entry(natural_text: str) -> dict[str, Any]:
    client = _openai_client()
    if client:
        prompt = (
            "You are PeakFuel parser. Split the input into one or more log entries when needed. "
            "Return JSON with key 'entries' where each entry has: type, confidence, and data. "
            "Allowed types: workout, hike, food, note. "
            "For workout use keys: date, workout_name, muscle_group, duration_minutes, cardio_minutes, estimated_calories_burned, notes, original_text, exercises[]. "
            "For hike use keys: date, trail_name, distance_miles, duration_minutes, elevation_gain_ft, estimated_calories_burned, difficulty, notes, original_text. "
            "For food use keys: date, meal_type, foods[], total_calories, total_protein, total_carbs, total_fat, notes, original_text. "
            "Each foods[] item must be an object with keys: item_name, estimated_calories, protein_g, carbs_g, fat_g. "
            "Provide calorie estimates whenever possible. For food, assume one serving per item unless quantity is explicitly stated; if quantity is stated, scale estimates accordingly. "
            "Include missing fields as null. Keep date as YYYY-MM-DD; default today if ambiguous."
        )
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": natural_text},
                ],
                temperature=0.1,
            )
            content = resp.choices[0].message.content or "{}"
            parsed = _safe_json(content)
            entries = parsed.get("entries", [])
            if not isinstance(entries, list):
                entries = []
            normalized = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                data = entry.get("data") or {}
                if not isinstance(data, dict):
                    data = {}
                if entry.get("type") == "food":
                    foods = data.get("foods")
                    if isinstance(foods, list):
                        normalized_foods = []
                        for food in foods:
                            if isinstance(food, str):
                                normalized_foods.append(
                                    {"item_name": food, "estimated_calories": None, "protein_g": None, "carbs_g": None, "fat_g": None}
                                )
                            elif isinstance(food, dict):
                                normalized_foods.append(
                                    {
                                        "item_name": food.get("item_name"),
                                        "estimated_calories": food.get("estimated_calories"),
                                        "protein_g": food.get("protein_g"),
                                        "carbs_g": food.get("carbs_g"),
                                        "fat_g": food.get("fat_g"),
                                    }
                                )
                        data["foods"] = normalized_foods
                data.setdefault("original_text", natural_text)
                normalized.append(
                    {
                        "type": entry.get("type", "note"),
                        "confidence": entry.get("confidence", 0.0),
                        "data": data,
                    }
                )
            if normalized:
                return {"entries": normalized}
        except Exception:
            pass
    return heuristic_parse_multi(natural_text)


def transcribe_audio(uploaded_file) -> str:
    client = _openai_client()
    if not client:
        return ""
    try:
        transcript = client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=uploaded_file)
        return getattr(transcript, "text", "") or ""
    except Exception:
        return ""


def heuristic_parse(text: str) -> dict[str, Any]:
    lower = text.lower()
    today = str(date.today())

    if any(k in lower for k in ["hike", "trail", "elevation", "miles"]):
        miles = _first_float(lower, r"(\d+(?:\.\d+)?)\s*(?:mile|mi)")
        elev = _first_int(lower, r"(\d{2,5})\s*(?:ft|feet)")
        dur = _duration_minutes(lower)
        return {
            "type": "hike",
            "confidence": 0.62,
            "data": {
                "date": today,
                "trail_name": "General Hike",
                "distance_miles": miles,
                "duration_minutes": dur,
                "elevation_gain_ft": elev,
                "difficulty": None,
                "notes": text,
                "original_text": text,
            },
        }

    if any(k in lower for k in ["ate", "breakfast", "lunch", "dinner", "protein shake", "sandwich"]):
        meal = "lunch" if "lunch" in lower else "dinner" if "dinner" in lower else "breakfast" if "breakfast" in lower else "snack"
        items = [{"item_name": token.strip().title(), "estimated_calories": None, "protein_g": None, "carbs_g": None, "fat_g": None} for token in re.split(r",| and ", text)[:4]]
        return {
            "type": "food",
            "confidence": 0.55,
            "data": {
                "date": today,
                "meal_type": meal,
                "foods": items,
                "total_calories": None,
                "total_protein": None,
                "total_carbs": None,
                "total_fat": None,
                "notes": text,
                "original_text": text,
            },
        }

    exercises = []
    for part in re.split(r",| then ", text):
        s = _first_int(part, r"(\d+)\s*(?:sets|x)")
        r = _first_int(part, r"(?:sets?\s*of\s*|x)(\d+)")
        w = _first_float(part, r"at\s*(\d+(?:\.\d+)?)")
        name = re.sub(r"\d.*", "", part).strip().title()
        if name and (s or r):
            exercises.append({"exercise_name": name, "sets": s, "reps": r, "weight": w})

    return {
        "type": "workout",
        "confidence": 0.5,
        "data": {
            "date": today,
            "workout_name": "Workout Session",
            "muscle_group": "general",
            "duration_minutes": _duration_minutes(lower),
            "exercises": exercises,
            "cardio_minutes": _first_int(lower, r"(\d+)\s*minutes?\s*(?:incline|run|cardio|treadmill)?"),
            "notes": text,
            "original_text": text,
        },
    }


def heuristic_parse_multi(text: str) -> dict[str, Any]:
    chunks = [c.strip() for c in re.split(r"[.\n]+| then ", text) if c.strip()]
    entries: list[dict[str, Any]] = []
    for chunk in chunks:
        parsed = heuristic_parse(chunk)
        if parsed.get("type") == "note":
            continue
        entries.append(parsed)
    if not entries:
        entries = [heuristic_parse(text)]
    return {"entries": entries}


def _first_int(text: str, pattern: str):
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _first_float(text: str, pattern: str):
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def _duration_minutes(text: str):
    hours = _first_int(text, r"(\d+)\s*hour") or 0
    mins = _first_int(text, r"(\d+)\s*min") or 0
    total = hours * 60 + mins
    return total if total > 0 else None
