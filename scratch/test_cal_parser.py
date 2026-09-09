import re

MONTHS = r'(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)'

test_queries = [
    'add a reminder in my calander of 15 sep about my birthday in google calender',
    'add a reminder of 15 sep about my birthday in google calender',
    'add a reminder for my birthday on 15 september in google calendar',
    'add a reminder to call mom tomorrow at 4pm',
    'remind me on 15 sep about my birthday',
    'add my birthday on 15 sep to my google calendar',
    'add meeting with Alex on Friday at 3pm to my calendar',
    'schedule meeting with Alex on Friday at 3pm',
    'set a reminder to buy groceries in 10 minutes',
    'what are my reminders',
    "what's on my calendar",
    'delete reminder buy groceries',
    'delete calendar event meeting with Alex'
]

def parse_cal_rem(request: str):
    req = request.strip()
    req_lower = req.lower().strip("?!., \t")
    
    # 1. Listing reminders
    if any(req_lower == k or req_lower.startswith(k + " ") for k in [
        "what are my reminders", "what are the reminders", "show my reminders", "show reminders",
        "list my reminders", "list reminders", "do i have any reminders", "check my reminders",
        "get my reminders", "get reminders", "my reminders"
    ]):
        return {"action": "list_reminders", "params": {"status": "pending"}}

    # 2. Listing calendar events
    if any(req_lower == k or req_lower.startswith(k + " ") for k in [
        "what is on my calendar", "what's on my calendar", "whats on my calendar",
        "show my calendar", "show calendar", "list calendar", "list my calendar",
        "what are my events", "show my events", "list events", "check my calendar",
        "what do i have scheduled", "what is scheduled", "my calendar", "my schedule"
    ]):
        return {"action": "list_calendar_events", "params": {"date": ""}}

    # 3. Deleting reminders
    del_rem_m = re.match(r'^(?:delete|remove|cancel|clear)\s+(?:the\s+|my\s+)?reminder(?:\s+for|\s+to|\s+called|\s*:|\s+)?\s*(.+)$', req, re.IGNORECASE)
    if del_rem_m:
        return {"action": "delete_reminder", "params": {"target": del_rem_m.group(1).strip()}}

    # 4. Deleting calendar events
    del_cal_m = re.match(r'^(?:delete|remove|cancel|clear)\s+(?:the\s+|my\s+)?(?:calendar\s+event|event|calendar\s+entry)(?:\s+for|\s+to|\s+called|\s*:|\s+)?\s*(.+)$', req, re.IGNORECASE)
    if del_cal_m:
        return {"action": "delete_calendar_event", "params": {"target": del_cal_m.group(1).strip()}}

    # 5. Adding reminder / calendar event (Flexible natural language parser)
    cal_pattern = r'\b(?:google\s+)?(?:calendar|calander|calender|calndar|cal)\b'
    is_calendar_query = bool(re.search(cal_pattern, req, re.IGNORECASE))
    is_reminder_query = bool(re.search(r'\b(?:reminder|remind\s+me|remember)\b', req, re.IGNORECASE))
    is_schedule_query = bool(re.search(r'\b(?:schedule|add\s+event|create\s+event)\b', req, re.IGNORECASE))
    is_google = bool(re.search(r'\bgoogle\b', req, re.IGNORECASE))

    if is_calendar_query or is_reminder_query or is_schedule_query:
        # Clean target calendar wording
        clean = re.sub(r'\b(?:in|on|to|into)\s+(?:my\s+)?(?:google\s+)?(?:calendar|calander|calender|calndar)\b', '', req, flags=re.IGNORECASE).strip()
        clean = re.sub(r'\b(?:google\s+)?(?:calendar|calander|calender|calndar)\b', '', clean, flags=re.IGNORECASE).strip()

        # Extract date/time pattern
        date_patterns = [
            rf'\b(?:of|on|for|at|in)?\s*(\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTHS}(?:\s+at\s+\S+)?)\b',
            rf'\b(?:of|on|for|at|in)?\s*({MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s+at\s+\S+)?)\b',
            rf'\b(?:of|on|for|at|in)?\s*(\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?(?:\s+at\s+\S+)?)\b',
            r'\b(?:of|on|for|at|in)?\s*((?:tomorrow|today|tonight)(?:\s+at\s+\S+)?)\b',
            r'\b(?:of|on|for|at|in)?\s*((?:next\s+\w+|\w+day)(?:\s+at\s+\S+)?)\b',
            r'\b(in\s+\d+\s*(?:min|minute|minutes|hr|hour|hours))\b',
            r'\b(?:at|on)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b',
        ]

        date_part = ''
        span = None
        for pat in date_patterns:
            m = re.search(pat, clean, re.IGNORECASE)
            if m:
                date_part = m.group(1).strip()
                span = m.span(0)
                break

        if span:
            subject = (clean[:span[0]] + ' ' + clean[span[1]:]).strip()
        else:
            subject = clean

        # Clean subject
        subject = re.sub(r'^(?:add|put|set|create|schedule|remind\s+me)\s+(?:a\s+)?(?:reminder|task)?\s*(?:about|for|to)?', '', subject, flags=re.IGNORECASE)
        subject = re.sub(r'^(?:about|for|to)\s+', '', subject.strip(), flags=re.IGNORECASE).strip()
        subject = re.sub(r'\s+(?:about|for|to)$', '', subject.strip(), flags=re.IGNORECASE).strip()
        if subject.lower() in ("my birthday", "birthday"):
            subject = "Birthday"
        if not subject:
            subject = "Reminder"

        if is_calendar_query or is_schedule_query:
            return {
                "action": "add_calendar_event",
                "params": {
                    "title": subject,
                    "date_str": date_part,
                    "time_str": "",
                    "open_google_calendar": is_google,
                }
            }
        else:
            return {
                "action": "set_reminder",
                "params": {
                    "text": subject,
                    "date_str": date_part,
                    "time_str": date_part,
                }
            }
    return None

for q in test_queries:
    res = parse_cal_rem(q)
    print(f"{q}\n  -> {res}\n")
