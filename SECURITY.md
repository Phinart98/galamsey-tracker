# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| main branch | Yes |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email phinart98@gmail.com with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix

You will receive an acknowledgment within 48 hours and a full response within
7 days. We will coordinate a fix and disclosure timeline with you.

## Scope

In-scope:
- Authentication bypass or privilege escalation in the API or moderator queue
- Exposure of citizen reporter identities or private location data
- SQL injection or other injection vulnerabilities
- Stored XSS in the citizen report or incident display

Out of scope:
- Rate limiting on public read endpoints
- Theoretical attacks with no realistic exploit path
- Issues in third-party dependencies not yet patched upstream

## Privacy note

Citizen reporters' identities are never stored publicly. EXIF metadata is
stripped from uploaded photos before storage (GPS coordinates are preserved
separately in the database and displayed at reduced precision). If you find a
path that exposes reporter identity, treat it as high-severity.
