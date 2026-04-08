# SAURON — Red Team Notes

SAURON includes a Red Team mode focused on **detection testing** for
blue teams and authorised engagements. It exists to exercise the
defender's SOC pipeline with realistic, stealthy, auditable traffic.

## What SAURON DOES ship
- **Stealth profiles** — `silent`, `normal`, `aggressive` — tune scan
  timing (`-T1` … `-T4`), add jitter, randomise source ports, and
  rotate user agents for HTTP tooling.
- **Operator narrative** — each action is accompanied by the attacker
  reasoning and the expected SOC signal, which becomes part of the
  after-action deliverable.
- **Asciinema recordings** — every PTY session is recorded, so the
  blue team can replay exactly what the red team did and at what time.
- **Living-off-the-land encouragement** — the Red Team agent is
  prompted to prefer on-target tooling over installing new binaries.
- **C2 interoperability hooks** — SAURON can orchestrate a human-
  supplied, authorised C2 (you configure the listener; SAURON never
  ships one).

## What SAURON DOES NOT ship
- No malware.
- No shellcode, reflective loaders, or droppers.
- No persistence implants.
- No EDR-disable tooling or signed-driver abuse.
- No anti-forensics or log-wiping utilities.
- No payload generators of any kind.

These omissions are deliberate. SAURON is a productivity multiplier
for authorised offensive work that uses **existing public tooling**,
not a framework to build custom offensive capability. If your
engagement needs payloads, your team brings and runs them under the
engagement's written authorisation; SAURON will orchestrate the
surrounding activity and document everything.

## Stealth profile knobs

| Profile    | Timing | Jitter         | UA rot. | Src-port rand. | Parallelism |
|---|---|---|---|---|---|
| silent     | T1     | 2000–8000 ms   | yes     | yes            | 2           |
| normal     | T3     | 200–1500 ms    | yes     | no             | 8           |
| aggressive | T4     | 0–100 ms       | no      | no             | 32          |

Override per-engagement in the dashboard or programmatically via
`config/default.yaml::stealth`.

## Authorisation is mandatory

You **must** have written authorisation to test any target. SAURON
records every command and every AI decision precisely so that you can
prove what was done, when, and why. Use that audit trail to protect
yourself and your client.
