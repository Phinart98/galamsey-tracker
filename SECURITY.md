# Security Policy

## Supported versions

Only the `master` branch and the site built from it are supported.

## Reporting a vulnerability

Please do not open a public GitHub issue for security problems.

Email hello@galamseytracker.org with:
- what the problem is
- how to reproduce it
- what an attacker could do with it
- a suggested fix, if you have one

You will get a reply within 7 days, and we will agree on a fix and when to disclose it.

## Scope

The project is a static website and a scheduled GitHub Actions job. It has no server, database, user accounts or upload forms.

In scope:
- Ways to read or misuse the workflow's secrets (NASA Earthdata login, Cloudflare token)
- Ways to change what the weekly job publishes without a commit to this repository, for example through the `pipeline-state` release or a dependency
- Script injection on the published site

Out of scope:
- Problems in third-party services the job reads from (NASA, Earth Search, OpenStreetMap, the Minerals Commission portal)
- Theoretical attacks with no realistic way to carry them out
