# Acme Technologies - Incident Response Playbook

Version: 2026.1

Document owner: Security and Reliability

Effective date: January 1, 2026

## Table of Contents

1. Purpose
2. Severity Definitions
3. Escalation Matrix
4. Incident Response Lifecycle
5. Communication
6. Recovery
7. Postmortems
8. On-Call Responsibilities
9. Related Documents

## 1. Purpose

This playbook defines how Acme Technologies detects, escalates, manages, resolves, and reviews operational and security incidents. It applies to production systems, customer-impacting internal services, security events, and incidents that may affect confidentiality, integrity, or availability.

Operational checks, readiness behavior, backups, and disaster recovery procedures are defined in the Acme Technologies Cloud Operations Runbook. Security reporting requirements are defined in the Acme Technologies Information Security Policy.

## 2. Severity Definitions

### 2.1 SEV-1 Critical

A SEV-1 incident is a critical event with major customer impact, active security compromise, data exposure, complete production outage, or significant regulatory risk.

Examples:

- Production platform unavailable for most customers.
- Confirmed unauthorized access to customer data.
- Loss of production database write capability.
- Active credential compromise affecting production systems.

SEV-1 incidents require immediate escalation, incident commander assignment, executive notification, and continuous response until mitigated.

### 2.2 SEV-2 High

A SEV-2 incident is a serious degradation, partial outage, suspected security exposure, or failure affecting an important customer segment.

Examples:

- Significant increase in API errors.
- Failed backups for a production database.
- Suspected but unconfirmed unauthorized access.
- Degraded retrieval or generation path affecting a major workflow.

### 2.3 SEV-3 Medium

A SEV-3 incident affects limited users, has a workaround, or presents low immediate risk but requires coordinated response.

### 2.4 SEV-4 Low

A SEV-4 incident is a minor operational issue, documentation error, or non-urgent follow-up with limited user impact.

## 3. Escalation Matrix

| Severity | Incident Commander | Notify Immediately | Update Cadence |
| --- | --- | --- | --- |
| SEV-1 | On-call engineering lead | CTO, Security lead, Customer Success lead, Legal if data exposure is possible | Every 15 minutes |
| SEV-2 | Service owner or on-call lead | Engineering manager, Security for security-related events, Customer Success if customers are affected | Every 30 minutes |
| SEV-3 | Service owner | Owning team and support channel | Every 2 hours |
| SEV-4 | Ticket owner | Owning team | As needed |

The incident commander owns coordination. The technical lead owns diagnosis and mitigation. Communications owns customer and stakeholder updates.

## 4. Incident Response Lifecycle

Acme Technologies uses six incident phases.

### 4.1 Detect

Incidents may be detected by alerts, customer reports, employee reports, monitoring dashboards, provider status pages, or security tooling.

### 4.2 Triage

The on-call responder assigns severity, identifies affected systems, confirms whether customer or security impact exists, and creates an incident channel.

### 4.3 Contain

The team limits blast radius. Containment may include disabling a feature, revoking credentials, scaling capacity, pausing deployments, blocking traffic, or isolating a system.

### 4.4 Mitigate

The team restores acceptable service or reduces risk. Mitigation may include rollback, failover, hotfix, provider workaround, configuration rollback, or manual customer support process.

### 4.5 Recover

The team verifies system health, data integrity, backlog processing, and customer-facing behavior. Follow the Cloud Operations Runbook for health checks, readiness checks, backup validation, and recovery verification.

### 4.6 Review

The team completes a postmortem for SEV-1, SEV-2, and recurring SEV-3 incidents.

## 5. Communication

Incident communication must be timely, factual, and concise.

Internal updates should include:

- Current severity.
- Customer impact.
- Systems affected.
- Current hypothesis.
- Mitigation underway.
- Next update time.

External customer communication must be approved by Customer Success and Legal when data exposure, contractual commitments, or regulatory reporting may apply.

Do not speculate about root cause before evidence is available. Do not include secrets, customer document contents, internal credentials, or vulnerability details in broad channels.

## 6. Recovery

Before an incident is resolved, the incident commander must confirm:

- Primary customer impact has ended.
- Error rates and latency returned to acceptable range.
- `/health` and `/ready` checks pass for affected services where applicable.
- Backlogs are draining or have been cleared.
- Data integrity has been assessed.
- Temporary access or emergency credentials are revoked.
- Monitoring is in place for recurrence.

Recovery steps for databases, backups, and maintenance windows are defined in the Cloud Operations Runbook.

## 7. Postmortems

Postmortems are required for SEV-1, SEV-2, and recurring SEV-3 incidents. They must be completed within five business days.

A postmortem must include:

- Summary.
- Timeline.
- Customer impact.
- Root cause.
- Detection source.
- What worked well.
- What made response harder.
- Corrective actions with owners and due dates.
- Follow-up validation plan.

Postmortems are blameless. The goal is to improve systems and response quality, not assign personal blame.

## 8. On-Call Responsibilities

On-call responders must:

- Acknowledge pages within five minutes.
- Triage severity and customer impact.
- Escalate when they lack access, expertise, or confidence.
- Start an incident channel for SEV-1 and SEV-2 events.
- Preserve relevant logs and timelines.
- Avoid risky production changes without commander approval.

Employees outside the on-call rotation should report urgent production or security concerns through the escalation path rather than directly changing production systems.

## 9. Related Documents

Use this playbook with:

- Acme Technologies - Cloud Operations Runbook.
- Acme Technologies - Information Security Policy.
- Acme Technologies - Engineering Handbook.
- Acme Technologies - Employee Handbook.
