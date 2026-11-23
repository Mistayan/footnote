"""Synthetic source notes and held-out task answers for the #605 pilot."""

DATE = "2026-11-23"
NEAR_SCOPE = "paper-mill"

# Each case pairs the same retrieval keyword across projects with a conflicting decision.
CASES = (
    {
        "scope": "glasshouse", "query": "calibration",
        "note": (
            "Glasshouse calibration meeting took place after a long inventory walk. The group reviewed the old "
            "shelving layouts, three vendor brochures, and the labels used for diagrams in the shared training folder. "
            "Glasshouse must hold calibration job CAL-71 until a technician signs seal QA-14. "
            "The first eligible date is 2026-12-04. Archive reference GL-119B."
        ),
        "near": "Paper-mill calibration job CAL-17 may run without any signature on 2026-12-01. Archive reference PM-19B.",
        "task": "Dispatch is asking about calibration in Glasshouse. No technician has signed the seal. What action, job and seal apply?",
        "initial": {"scope": "glasshouse", "action": "hold", "job": "CAL-71", "seal": "QA-14"},
        "follow_up": "Assuming the signature arrives, what is the first eligible date and the archive reference?",
        "later": {"first_date": "2026-12-04", "archive_ref": "GL-119B"},
        "evidence": {"scope": "glasshouse", "action": "must hold", "job": "CAL-71", "seal": "QA-14", "trigger": "until a technician signs", "first_date": "2026-12-04", "archive_ref": "GL-119B"},
    },
    {
        "scope": "windward", "query": "manifest",
        "note": (
            "Windward must never email manifest MF-208 externally unless privacy approval PA-09 is recorded. "
            "The team chose the wording after discussing routine coordination, sample email subject lines, and which "
            "parts of a holiday checklist everyone could see on the noticeboard. Archive reference WW-63C."
        ),
        "near": "Paper-mill may always email manifest MF-280 externally without approval. Archive reference PM-63C.",
        "task": "A vendor requests Windward's manifest by email. There is no recorded privacy approval. What action, manifest and approval apply?",
        "initial": {"scope": "windward", "action": "deny", "manifest": "MF-208", "approval": "PA-09"},
        "follow_up": "PA-09 has now been recorded. Is external email allowed, and which archive reference should I enter?",
        "later": {"action": "allow", "archive_ref": "WW-63C"},
        "evidence": {"scope": "windward", "action": "never email", "manifest": "MF-208", "approval": "PA-09", "trigger": "unless privacy approval", "archive_ref": "WW-63C"},
    },
    {
        "scope": "greywater", "query": "transfer",
        "note": (
            "Greywater may transfer batch TR-604 to bay B-12 before 18:00 UTC on 2026-12-08. "
            "Greywater must hold the transfer if sensor S-50 reports 7 ppm or more. Archive reference GW-42A. "
            "The shift lead also discussed lunch schedules and the decorative stripes on the replacement tote."
        ),
        "near": "Paper-mill may transfer batch TR-640 to bay B-21 when sensor S-05 reports 9 ppm or less. Archive reference PM-42A.",
        "task": "Greywater needs a transfer decision at 17:45 UTC on 2026-12-08. The relevant sensor reads exactly 7 ppm. Return the action, batch and sensor.",
        "initial": {"scope": "greywater", "action": "hold", "batch": "TR-604", "sensor": "S-50"},
        "follow_up": "It is now 17:50 UTC that day and the sensor is at 6 ppm. What is the action, destination bay and archive reference?",
        "later": {"action": "allow", "bay": "B-12", "archive_ref": "GW-42A"},
        "evidence": {"scope": "greywater", "action": "must hold", "batch": "TR-604", "sensor": "S-50", "trigger": "7 ppm or more", "date": "2026-12-08", "deadline": "18:00 UTC", "bay": "B-12", "archive_ref": "GW-42A"},
    },
    {
        "scope": "redwood", "query": "purge",
        "note": (
            "Redwood purge planning included an afternoon meeting about stationery, corridor seating and a table "
            "of inventory counts from a retired inventory workbook used for a workshop three seasons ago. "
            "Redwood must not purge cartridge BX-17 before 2026-12-19, even with clearance CL-22. "
            "From that date, Redwood may purge BX-17 only with CL-22. Archive reference RW-26D."
        ),
        "near": "Paper-mill may purge cartridge BX-71 with clearance CL-22 before 2026-12-12. Archive reference PM-26D.",
        "task": "A Redwood supervisor asks to purge a cartridge on 2026-12-18 and has clearance. Return the action, cartridge and clearance code.",
        "initial": {"scope": "redwood", "action": "deny", "cartridge": "BX-17", "clearance": "CL-22"},
        "follow_up": "It is 2026-12-19. The clearance was withdrawn. Can the purge proceed, and what is the earliest eligible date with clearance?",
        "later": {"action": "deny", "first_date": "2026-12-19"},
        "evidence": {"scope": "redwood", "action": "must not purge", "cartridge": "BX-17", "clearance": "CL-22", "trigger": "only with CL-22", "date": "2026-12-19"},
    },
)
