# SECURE — Personal & Health Data Policy

This repository is a public product (`syst0m/demiurge`) and is publicly readable
on GitHub. It must not contain anyone's private, health, or identity-adjacent
data.

## The rule

- **No personal or health data in this repo.** That includes personal protocols,
  symptom logs, medication details, clinician contacts, crisis lines, emergency
  plans, names, addresses, phone numbers, emails, and local Windows `C:\Users\...`
  paths.
- **Private data + a writable public repo in one place is exploitable.** Personal health protocols committed here are personal health information. It was
  pushed to the public repo and indexed on GitHub. Removing it from GitHub's
  index/history is a separate operation; do not assume it is gone because this
  file is untracked.
- Personal regimens belong outside this repo: on a private device, an offline
  notes file, or a private repo the owner controls.

## Enforcement

- `scripts/scan_security_and_pii.py` refuses commits that carry the markers below
  (emails, phones, local Windows/Unix paths, secrets) as well as personal
  markers loaded from `scripts/local_pii_patterns.py` (gitignored — never
  committed). Populate that file with your own name, medications, and crisis
  keywords; the public scanner intentionally carries no personal keywords.
- `scripts/local_pii_patterns.py.example` shows the format.
- The health markers are a heuristic. Human review of any health/clinic-specific
  content that touches this repo remains the final gate.
- `.gitignore` keeps `protocols/<personal-health-protocol>/` and
  `routines/<personal-health-loop>.md` out of version control.

## What NOT to commit

| Category | Examples |
| --- | --- |
| Health regimens | personal health protocols, symptom logs, medication matrices |
| Clinical contacts | prescriber, therapist, crisis line, safe contacts, emergency plan |
| Identity/history | names, addresses, phone, email, local `C:\Users\...` |
| Session artifacts | transcripts, eval results, `.judge` notes holding personal prompts |

Run `python scripts/scan_security_and_pii.py` before every commit.
