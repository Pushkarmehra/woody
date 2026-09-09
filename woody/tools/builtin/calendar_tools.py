"""
Calendar & Reminders Tools — Task scheduling, calendar events, and reminders for Woody.

Provides tools to:
- Add calendar events with natural language date/time parsing
- Set persistent reminders with scheduled notifications
- List, query, and delete calendar events and reminders
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from woody.utils.logging import get_logger

log = get_logger(__name__)

CALENDAR_FILE = Path("~/.Woody/calendar_events.json").expanduser()
REMINDERS_FILE = Path("~/.Woody/reminders.json").expanduser()

TOOLS = [
    "add_calendar_event",
    "set_reminder",
    "list_calendar_events",
    "list_reminders",
    "delete_reminder",
    "delete_calendar_event",
]


def _ensure_storage() -> None:
    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CALENDAR_FILE.exists():
        with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not REMINDERS_FILE.exists():
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def _load_events() -> list[dict]:
    _ensure_storage()
    try:
        with open(CALENDAR_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_events(events: list[dict]) -> None:
    _ensure_storage()
    with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)


def _load_reminders() -> list[dict]:
    _ensure_storage()
    try:
        with open(REMINDERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_reminders(reminders: list[dict]) -> None:
    _ensure_storage()
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2)


MONTH_MAP: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _parse_natural_datetime(date_str: str = "", time_str: str = "") -> datetime.datetime:
    """Parse common natural date and time strings into a datetime object."""
    now = datetime.datetime.now()
    target_date = now.date()

    d_clean = date_str.lower().strip()
    t_clean = time_str.lower().strip()
    combo = f"{d_clean} {t_clean}".strip()

    # Relative minutes/hours: "in 10 minutes", "in 2 hours", "in 30 mins"
    in_min_m = re.search(r'in\s+(\d+)\s*(?:min|minute|minutes|m\b)', combo)
    if in_min_m:
        mins = int(in_min_m.group(1))
        return now + datetime.timedelta(minutes=mins)

    in_hr_m = re.search(r'in\s+(\d+)\s*(?:hr|hour|hours|h\b)', combo)
    if in_hr_m:
        hrs = int(in_hr_m.group(1))
        return now + datetime.timedelta(hours=hrs)

    date_matched = False

    # 1. Month names + day number: "15 sep", "15th september", "15 of sept", "sep 15", "september 15th"
    m_d1 = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)\b', combo)
    if m_d1 and m_d1.group(2).lower() in MONTH_MAP:
        day = int(m_d1.group(1))
        month = MONTH_MAP[m_d1.group(2).lower()]
        year = now.year
        try:
            cand = datetime.date(year, month, day)
            if cand < now.date() and (now.date() - cand).days > 60:
                cand = datetime.date(year + 1, month, day)
            target_date = cand
            date_matched = True
        except ValueError:
            pass

    if not date_matched:
        m_d2 = re.search(r'\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b', combo)
        if m_d2 and m_d2.group(1).lower() in MONTH_MAP:
            day = int(m_d2.group(2))
            month = MONTH_MAP[m_d2.group(1).lower()]
            year = now.year
            try:
                cand = datetime.date(year, month, day)
                if cand < now.date() and (now.date() - cand).days > 60:
                    cand = datetime.date(year + 1, month, day)
                target_date = cand
                date_matched = True
            except ValueError:
                pass

    if not date_matched:
        m_d3 = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', combo)
        if m_d3:
            day = int(m_d3.group(1))
            month = int(m_d3.group(2))
            year = int(m_d3.group(3)) if m_d3.group(3) else now.year
            if year < 100:
                year += 2000
            try:
                cand = datetime.date(year, month, day)
                if cand < now.date() and (now.date() - cand).days > 60:
                    cand = datetime.date(year + 1, month, day)
                target_date = cand
                date_matched = True
            except ValueError:
                pass

    if not date_matched:
        # Relative days
        if "tomorrow" in d_clean or "tomorrow" in t_clean:
            target_date = now.date() + datetime.timedelta(days=1)
        elif "day after tomorrow" in d_clean or "day after tomorrow" in t_clean:
            target_date = now.date() + datetime.timedelta(days=2)
        elif "today" in d_clean or "tonight" in d_clean:
            target_date = now.date()
        else:
            # Check weekdays
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for idx, w in enumerate(weekdays):
                if w in d_clean or w in t_clean:
                    days_ahead = (idx - now.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date = now.date() + datetime.timedelta(days=days_ahead)
                    break

    # Time parsing: strip only actual month-day patterns first so day numbers aren't confused with hours
    month_pat = r'(?:' + '|'.join(MONTH_MAP.keys()) + r')'
    clean_time_str = re.sub(rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{month_pat}\b', '', combo, flags=re.IGNORECASE)
    clean_time_str = re.sub(rf'\b{month_pat}\s+\d{{1,2}}(?:st|nd|rd|th)?\b', '', clean_time_str, flags=re.IGNORECASE)
    clean_time_str = re.sub(r'\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b', '', clean_time_str, flags=re.IGNORECASE)

    target_hour = 9  # Default to 9:00 AM for scheduled events
    target_min = 0

    # Match 12-hour or 24-hour time e.g. "3pm", "3:30pm", "15:00", "9 am", "11:30"
    time_m = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', clean_time_str)
    if time_m:
        h = int(time_m.group(1))
        m = int(time_m.group(2) or 0)
        ampm = (time_m.group(3) or "").lower()

        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        elif not ampm and "tonight" in combo and h < 12:
            h += 12

        if h <= 23 and m <= 59:
            target_hour = h
            target_min = m

    return datetime.datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=target_hour,
        minute=target_min,
    )


def add_calendar_event(
    title: str,
    date_str: str = "",
    time_str: str = "",
    duration_minutes: int = 30,
    description: str = "",
    open_app: bool = False,
    open_google_calendar: bool = False,
) -> dict[str, Any]:
    """
    Add an event to the calendar.

    Args:
        title: Event title / meeting name.
        date_str: Date string (e.g. '15 sep', 'tomorrow', 'Monday', '2026-09-15').
        time_str: Time string (e.g. '3pm', '10:30am').
        duration_minutes: Duration in minutes (default 30).
        description: Optional notes/description.
        open_app: If true, opens Windows Calendar (default False).
        open_google_calendar: If true, opens event pre-filled in Google Calendar (default False).
    """
    dt = _parse_natural_datetime(date_str=date_str, time_str=time_str)
    end_dt = dt + datetime.timedelta(minutes=duration_minutes)

    event_id = str(uuid.uuid4())[:8]
    event = {
        "id": event_id,
        "title": title.strip(),
        "start_time": dt.strftime("%Y-%m-%d %H:%M"),
        "end_time": end_dt.strftime("%Y-%m-%d %H:%M"),
        "duration_minutes": duration_minutes,
        "description": description.strip(),
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    events = _load_events()
    events.append(event)
    _save_events(events)

    # Simultaneously register as a pending reminder
    reminder = {
        "id": event_id,
        "text": title.strip(),
        "remind_at": dt.strftime("%Y-%m-%d %H:%M"),
        "status": "pending",
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    reminders = _load_reminders()
    reminders.append(reminder)
    _save_reminders(reminders)

    gcal_opened = False
    if open_google_calendar:
        # Launch Google Calendar in exactly ONE browser tab/window
        try:
            import urllib.parse
            import webbrowser
            encoded_title = urllib.parse.quote_plus(title.strip())
            if time_str:
                dates_param = f"{dt.strftime('%Y%m%dT%H%M00')}/{end_dt.strftime('%Y%m%dT%H%M00')}"
            else:
                dates_param = f"{dt.strftime('%Y%m%d')}/{(dt + datetime.timedelta(days=1)).strftime('%Y%m%d')}"
            gcal_url = f"https://calendar.google.com/calendar/r/eventedit?text={encoded_title}&dates={dates_param}"
            webbrowser.open(gcal_url)
            gcal_opened = True
        except Exception as e:
            log.warning("calendar.google_open_error", error=str(e))

    elif open_app:
        try:
            os.startfile("ms-calendar:")
        except Exception:
            pass

    has_time = bool(time_str.strip()) or any(w in date_str.lower() for w in ["am", "pm", ":"])
    formatted_time = dt.strftime("%A, %b %d at %I:%M %p") if has_time else dt.strftime("%A, %b %d")

    if gcal_opened:
        msg = f"Added '{title}' on {formatted_time} to your calendar and opened Google Calendar."
    else:
        msg = f"Added '{title}' on {formatted_time} to your calendar."

    log.info("calendar.event_added", event_id=event_id, title=title, time=formatted_time, google=gcal_opened)

    return {
        "success": True,
        "action": "add_calendar_event",
        "event": event,
        "message": msg,
        "formatted_time": formatted_time,
        "google_calendar_opened": gcal_opened,
    }


def set_reminder(
    text: str,
    time_str: str = "",
    date_str: str = "",
) -> dict[str, Any]:
    """
    Set a scheduled reminder.

    Args:
        text: Reminder message (e.g. 'call mom', 'check the oven').
        time_str: Time or relative delay (e.g. 'in 10 minutes', '5pm').
        date_str: Optional date string (e.g. 'tomorrow', 'today').
    """
    dt = _parse_natural_datetime(date_str=date_str, time_str=time_str)
    reminder_id = str(uuid.uuid4())[:8]

    reminder = {
        "id": reminder_id,
        "text": text.strip(),
        "remind_at": dt.strftime("%Y-%m-%d %H:%M"),
        "status": "pending",
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    reminders = _load_reminders()
    reminders.append(reminder)
    _save_reminders(reminders)

    formatted_time = dt.strftime("%A, %b %d at %I:%M %p")
    now = datetime.datetime.now()
    diff_sec = (dt - now).total_seconds()

    msg = f"Reminder set: '{text}' for {formatted_time}."

    # If within 2 hours, schedule an async background task to trigger notification
    if 0 < diff_sec <= 7200:
        async def _notify_when_due():
            await asyncio.sleep(diff_sec)
            try:
                from woody.utils.logging import get_logger
                get_logger(__name__).info("reminder.triggered", text=text)
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_notify_when_due())
        except RuntimeError:
            pass

    log.info("calendar.reminder_set", id=reminder_id, text=text, time=formatted_time)

    return {
        "success": True,
        "action": "set_reminder",
        "reminder": reminder,
        "message": msg,
        "formatted_time": formatted_time,
    }


def list_calendar_events(date_str: str = "") -> dict[str, Any]:
    """List calendar events, optionally filtered by date query."""
    events = _load_events()
    if date_str:
        q = date_str.lower().strip()
        filtered = [e for e in events if q in e.get("start_time", "").lower() or q in e.get("title", "").lower()]
    else:
        filtered = events

    if not filtered:
        return {
            "success": True,
            "events": [],
            "message": "You have no upcoming calendar events scheduled.",
        }

    lines = [f"• {e['title']} — {e['start_time']}" for e in filtered[:5]]
    return {
        "success": True,
        "events": filtered,
        "count": len(filtered),
        "message": f"You have {len(filtered)} event(s) scheduled:\n" + "\n".join(lines),
    }


def list_reminders(status: str = "pending") -> dict[str, Any]:
    """List reminders, filtered by status ('pending' or 'all')."""
    reminders = _load_reminders()
    if status != "all":
        filtered = [r for r in reminders if r.get("status") == status]
    else:
        filtered = reminders

    if not filtered:
        return {
            "success": True,
            "reminders": [],
            "message": "You have no pending reminders.",
        }

    lines = [f"• {r['text']} (Due: {r['remind_at']})" for r in filtered[:5]]
    return {
        "success": True,
        "reminders": filtered,
        "count": len(filtered),
        "message": f"You have {len(filtered)} reminder(s):\n" + "\n".join(lines),
    }


def delete_reminder(target: str) -> dict[str, Any]:
    """Delete a reminder by ID or matching text."""
    reminders = _load_reminders()
    orig_len = len(reminders)
    t = target.lower().strip()

    reminders = [r for r in reminders if r.get("id") != t and t not in r.get("text", "").lower()]
    if len(reminders) < orig_len:
        _save_reminders(reminders)
        return {"success": True, "message": f"Deleted reminder matching '{target}'."}
    return {"success": False, "error": f"No reminder found matching '{target}'."}


def delete_calendar_event(target: str) -> dict[str, Any]:
    """Delete a calendar event by ID or title."""
    events = _load_events()
    orig_len = len(events)
    t = target.lower().strip()

    events = [e for e in events if e.get("id") != t and t not in e.get("title", "").lower()]
    if len(events) < orig_len:
        _save_events(events)
        return {"success": True, "message": f"Deleted calendar event matching '{target}'."}
    return {"success": False, "error": f"No calendar event found matching '{target}'."}
