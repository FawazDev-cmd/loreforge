# Acme Technologies - Cloud Operations Runbook

Version: 2026.1

Document owner: Reliability Engineering

Effective date: January 1, 2026

## Table of Contents

1. Infrastructure Overview
2. Health Checks
3. Readiness Checks
4. Monitoring
5. Alerting
6. Backups
7. Disaster Recovery
8. Maintenance Windows
9. Operational Change Control
10. Related Documents

## 1. Infrastructure Overview

Acme Technologies production services run on managed cloud infrastructure with separated application, database, and provider-integration layers. Services should be deployed through approved pipelines and configured through environment variables or managed secret stores.

The Engineering Handbook defines deployment approval requirements. The Information Security Policy defines encryption, access control, and credential handling requirements. The Incident Response Playbook defines escalation when infrastructure affects customers or security posture.

## 2. Health Checks

Applications must expose a liveness health endpoint when technically appropriate.

Health checks should answer whether the process is alive and able to respond to basic requests. They should not perform expensive dependency calls.

Minimum expectations:

- Endpoint path: `/health` unless an exception is approved.
- Response should be fast and deterministic.
- Response must not expose secrets, internal paths, provider payloads, or stack traces.
- Health failures should trigger service restart only when restart is a safe remediation.

Health does not prove that a service is ready to receive production traffic.

## 3. Readiness Checks

Applications that require startup initialization must expose a readiness endpoint.

Readiness should answer whether the application completed required startup work and can safely serve traffic.

Minimum expectations:

- Endpoint path: `/ready` unless an exception is approved.
- Return success only after required warm-up completes.
- Return unavailable while startup work is incomplete.
- Do not perform unnecessary live database, provider, or model calls inside the readiness request path.
- Mark readiness false before shutdown cleanup completes.

Examples of startup work include database connection setup, migration validation, provider configuration validation, local model warm-up, and cache initialization.

## 4. Monitoring

Production services must provide enough visibility to distinguish user error, application defects, infrastructure failures, and provider outages.

Monitoring should include:

- Request count by route and status family.
- Request duration.
- Error count by safe error category.
- Startup and shutdown events.
- Dependency initialization duration.
- Background job failures where applicable.
- Provider retry and exhaustion events.

Metric labels must be bounded. Do not use customer names, document names, prompts, email addresses, request bodies, or raw exception messages as metric labels.

## 5. Alerting

Alerts should be actionable. Every alert must have an owner, severity, routing path, and response note.

Recommended alert conditions:

- Production service unavailable.
- Readiness remains false after expected startup window.
- Error rate exceeds threshold for critical routes.
- Latency exceeds threshold for customer-facing routes.
- Database backup failure.
- Database replication lag or storage pressure.
- Provider failure rate exceeds threshold.

Alert severity should follow the Incident Response Playbook. A critical customer outage or confirmed data exposure must be treated as SEV-1.

## 6. Backups

Production databases must be backed up automatically.

Backup policy:

- Full database backups at least daily.
- Point-in-time recovery for production transactional data where supported.
- Backup encryption at rest.
- Backup access restricted to reliability and security owners.
- Restore test at least quarterly.
- Retention period of 35 days unless contract or regulation requires longer.

Backup failures for production databases are SEV-2 unless data loss is confirmed or customer impact is active, in which case severity may be raised.

## 7. Disaster Recovery

Disaster recovery planning must define recovery point objective, recovery time objective, owner, and validation procedure for each production service.

Minimum recovery expectations:

- Documented restore process.
- Known dependencies and provider assumptions.
- Validated backup restore procedure.
- Configuration and secret restoration plan.
- Customer communication plan for extended outage.
- Post-recovery data integrity checks.

Systems that depend on uploaded source files must define durable object storage or another approved rebuild source. Metadata and derived chunks alone are not sufficient for every rebuild scenario.

## 8. Maintenance Windows

Planned maintenance is required when a change may affect customer availability, data integrity, or production access.

Maintenance window requirements:

- Change owner.
- Customer impact statement.
- Start and end time.
- Rollback plan.
- Communication owner.
- Verification checklist.
- Incident escalation path.

Emergency maintenance during an active incident follows the Incident Response Playbook.

## 9. Operational Change Control

Operational changes must be reviewable and reversible when practical.

Changes requiring explicit approval:

- Production database migrations.
- Secret rotation affecting production services.
- Network access changes.
- Backup configuration changes.
- Provider model or API configuration changes.
- Changes to health, readiness, authentication, or authorization behavior.

After deployment, owners must verify health, readiness, expected logs, and key user flows.

## 10. Related Documents

Use this runbook with:

- Acme Technologies - Incident Response Playbook.
- Acme Technologies - Engineering Handbook.
- Acme Technologies - Information Security Policy.
- Acme Technologies - Employee Handbook.
