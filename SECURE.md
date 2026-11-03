# SECURE — Personal & Health Data Policy

This repository is a public product (`syst0m/demiurge`) and is publicly readable
on GitHub. It must not contain anyone's private, health, or identity-adjacent
data.

## The rule

- **No personal or health data in this repo.** That includes personal protocols,
  symptom logs, medication details, clinician contacts, crisis lines, emergency
  plans, names, addresses, phone numbers, emails, and local Windows `C:\Users\...`
  paths.
- **Private data + a writable public repo in one place is exploitable.** The
  AuDHD burnout protocol committed here is personal health information. It was
  pushed to the public repo and indexed on GitHub. Removing it from GitHub's
  index/history is a separate operation; do not assume it is gone because this
  file is untracked.
- Personal regimens belong outside this repo: on a private device, an offline
  notes file, or a private repo the owner controls.

## Enforcement

- `scripts/scan_security_and_pii.py` refuses commits that carry the markers below
  (emails, phones, prescription medication, crisis/self-harm content) as well as
  local path secrets. It is the pre-commit gate; it is extended with health
  markers to close this incident's gap.
- The health markers are a heuristic. Human review of any health/clinic-specific
  content that touches this repo remains the final gate.
- `.gitignore` keeps `protocols/auadhd-burnout/` and
  `routines/auadhd-burnout-loop.md` out of version control.

## What NOT to commit

| Category | Examples |
| --- | --- |
| Health regimens | burnout protocols, symptom logs, medication matrices |
| Clinical contacts | prescriber, therapist, crisis line, safe contacts, emergency plan |
| Identity/history | names, addresses, phone, email, local `C:\Users\...` |
| Session artifacts | transcripts, eval results, `.judge` notes holding personal prompts |

Run `python scripts/scan_security_and_pii.py` before every commit.
