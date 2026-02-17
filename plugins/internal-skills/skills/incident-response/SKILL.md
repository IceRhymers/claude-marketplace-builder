---
name: incident-response
description: >
  Guide incident response procedures including diagnostics gathering, runbook execution,
  stakeholder communication, and post-mortem creation. Use when handling production incidents,
  outages, or service degradation.
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

# Incident Response

## Overview

Guide on-call engineers through incident response: triage, diagnostics, communication, resolution, and post-mortem.

## Prerequisites

- Access to monitoring/alerting systems
- Access to production logs
- Familiarity with the escalation matrix in `references/escalation-matrix.md`

## Workflow

### Phase 1: Triage

<!-- TODO: Customize for your infrastructure -->

1. Identify the affected service(s)
2. Determine severity level (P1-P4)
3. Load the appropriate runbook from `references/`

### Phase 2: Diagnostics

<!-- TODO: Add your diagnostic scripts to scripts/ -->

1. Run diagnostics script:
   ```bash
   python scripts/gather_diagnostics.py --service <service-name>
   ```
2. Analyze log output for known error patterns
3. Check recent deployments and config changes

### Phase 3: Communication

<!-- TODO: Customize communication templates -->

1. Draft incident channel update using company template
2. Notify stakeholders per `references/escalation-matrix.md`

### Phase 4: Resolution & Post-Mortem

1. Apply fix or rollback per runbook
2. Verify recovery
3. Create post-mortem document

## Scripts

<!-- TODO: Add helper scripts -->
<!-- - `scripts/gather_diagnostics.py` — Collect logs and metrics from affected services -->

## References

<!-- TODO: Add runbooks and reference docs -->
<!-- - `references/escalation-matrix.md` — Who to notify and when -->
<!-- - `references/runbook-db-outage.md` — Database outage procedures -->
<!-- - `references/runbook-api-latency.md` — API latency degradation -->
<!-- - `references/postmortem-template.md` — Post-mortem document template -->

## Severity Levels

| Level | Criteria | Response Time | Escalation |
|-------|----------|---------------|------------|
| P1 | Service down, all users affected | Immediate | VP + on-call chain |
| P2 | Major degradation, many users | 15 min | Manager + team lead |
| P3 | Partial degradation, some users | 1 hour | Team lead |
| P4 | Minor issue, workaround exists | Next business day | Ticket |
