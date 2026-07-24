# Member 2 Demo Data Catalogue

All seed data is fictional and deterministic. Each service seeds only its own database and reset endpoint only resets that service.

## CRM Customers

| External ID | Name | Tier | ARR | Renewal | Active | Demo Purpose |
| --- | --- | --- | --- | --- | --- | --- |
| `CUS-ALPHA` | Alpha Bank | Enterprise | `600000.00` | `2026-09-22` | true | Active enterprise customer used by the main incident workflow |
| `CUS-NOVA` | Nova Retail | Enterprise | `1200000.00` | `2026-11-20` | true | High-value enterprise customer with in-progress incident |
| `CUS-GREEN` | GreenLogistics | Standard | `180000.00` | `2026-07-27` | true | Standard customer for filtering and search examples |
| `CUS-MEDI` | MediCore | Premium | `400000.00` | `2027-02-15` | true | Premium customer with resolved incident |
| `CUS-DORMANT` | Dormant Systems | Standard | `25000.00` | `2025-12-01` | false | Inactive customer example |

Demonstrates active customers, inactive customers, enterprise customers, premium customers, standard customers, search, tier filtering, and active filtering.

## Incidents

| External ID | Customer | Priority | Status | SLA Deadline | Specialist | Demo Purpose |
| --- | --- | --- | --- | --- | --- | --- |
| `INC-ALPHA-001` | `CUS-ALPHA` | `CRITICAL` | `OPEN` | `2026-07-22T12:00:00Z` | none | Open and overdue critical incident |
| `INC-NOVA-001` | `CUS-NOVA` | `HIGH` | `IN_PROGRESS` | `2099-07-25T10:00:00Z` | `SPEC-NIMAL` | In-progress incident with assigned specialist |
| `INC-GREEN-001` | `CUS-GREEN` | `MEDIUM` | `OPEN` | `2099-07-27T10:00:00Z` | none | Non-overdue open incident |
| `INC-MEDI-001` | `CUS-MEDI` | `LOW` | `RESOLVED` | `2026-07-23T10:00:00Z` | `SPEC-MAYA` | Resolved incident excluded from overdue filtering |
| `INC-OMEGA-001` | `CUS-OMEGA` | `HIGH` | `CLOSED` | `2026-07-21T18:00:00Z` | `SPEC-DANIEL` | Closed incident for terminal-state tests |

Demonstrates open incidents, overdue incidents, closed incidents, resolved incidents, assigned and unassigned incidents, priority filters, and status-transition conflicts.

## Specialists And Skills

| External ID | Name | Email | Skills | Capacity | Workload | Availability | Active | Demo Purpose |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `SPEC-MAYA` | Maya Sen | `maya.sen@example.test` | billing, technical, integration | 2 | 0 | true | true | Available multi-skilled specialist |
| `SPEC-DANIEL` | Daniel Ruiz | `daniel.ruiz@example.test` | technical, enterprise-support | 2 | 1 | true | true | Partially loaded technical specialist |
| `SPEC-NIMAL` | Nimal Perera | `nimal.perera@example.test` | security, integration | 1 | 1 | true | true | Full-capacity specialist |
| `SPEC-PRIYA` | Priya Raman | `priya.raman@example.test` | account-management, billing | 3 | 0 | false | true | Unavailable specialist |
| `SPEC-KAI` | Kai Morgan | `kai.morgan@example.test` | technical, security | 2 | 0 | true | false | Inactive specialist |

Demonstrates available specialists, unavailable specialists, inactive specialists, full-capacity specialists, multi-skilled specialists, skill filtering, and effective capacity.

## Reservations

| External ID | Specialist | Incident | Status | Important State | Demo Purpose |
| --- | --- | --- | --- | --- | --- |
| `RES-MAYA-PENDING` | `SPEC-MAYA` | `INC-ALPHA-001` | `PENDING` | Expires in 2099 | Pending reservation consumes effective capacity |
| `RES-DANIEL-CONFIRMED` | `SPEC-DANIEL` | `INC-NOVA-001` | `CONFIRMED` | Confirmed at `2026-07-22T10:02:00Z` | Confirmed reservation and workload accounting |
| `RES-NIMAL-CONFIRMED` | `SPEC-NIMAL` | `INC-MEDI-001` | `CONFIRMED` | Confirmed at `2026-07-22T10:03:00Z` | Full-capacity specialist state |
| `RES-PRIYA-CANCELLED` | `SPEC-PRIYA` | `INC-CANCELLED-001` | `CANCELLED` | Cancelled at `2026-07-22T10:04:00Z` | Cancelled reservation does not consume capacity |
| `RES-DANIEL-EXPIRED` | `SPEC-DANIEL` | `INC-EXPIRED-001` | expired `PENDING` | Expires in 2026 | Lazy expiration and confirm-conflict test |

Demonstrates pending reservation, confirmed reservation, cancelled reservation, expired reservation, duplicate active reservation conflict, capacity conflict, and idempotent confirmation/cancellation behavior.

## Assignment Requests

| External ID | Incident | Specialist | Status | Important State | Demo Purpose |
| --- | --- | --- | --- | --- | --- |
| `AR-PENDING-001` | `INC-ALPHA-001` | `SPEC-MAYA` | `PENDING` | Expires in 2099 | Pending assignment request |
| `AR-ACCEPTED-001` | `INC-NOVA-001` | `SPEC-DANIEL` | `ACCEPTED` | Response note `Available now.` | Accepted final response and opposite-response conflict |
| `AR-REJECTED-001` | `INC-MEDI-001` | `SPEC-NIMAL` | `REJECTED` | Response note `Capacity is already committed.` | Rejected final response |
| `AR-EXPIRED-001` | `INC-EXPIRED-001` | `SPEC-PRIYA` | expired `PENDING` | Expires in 2020 | Lazy expiration and cannot-answer conflict |
| `AR-CANCELLED-001` | `INC-CANCELLED-001` | `SPEC-KAI` | `CANCELLED` | Terminal state | Cancelled request cannot be answered |

Demonstrates pending, accepted, rejected, expired, and cancelled assignment-request states.

## Notifications

| External ID | Channel | Recipient | Status | Idempotency Key | Related Request | Demo Purpose |
| --- | --- | --- | --- | --- | --- | --- |
| `NOT-EMAIL-DELIVERED` | `EMAIL` | `maya.sen@example.test` | `DELIVERED` | `seed-email-ar-pending` | `AR-PENDING-001` | Delivered email notification |
| `NOT-SMS-DELIVERED` | `SMS` | `+15550101010` | `DELIVERED` | `seed-sms-ar-accepted` | `AR-ACCEPTED-001` | Delivered SMS notification |
| `NOT-INAPP-DELIVERED` | `IN_APP` | `SPEC-DANIEL` | `DELIVERED` | `seed-inapp-ar-accepted` | `AR-ACCEPTED-001` | Delivered in-app notification |
| `NOT-FAILED-001` | `EMAIL` | `fail@example.test` | `FAILED` | `seed-failed-email` | `AR-REJECTED-001` | Controlled failed delivery state |
| `NOT-WEBHOOK-DELIVERED` | `WEBHOOK` | `webhook-demo-destination` | `DELIVERED` | `seed-webhook-standalone` | none | Standalone delivered webhook simulation |

Demonstrates delivered notification, failed notification, channel filtering, status filtering, idempotency replay, and idempotency conflict behavior.

## Reset Order

Recommended deterministic reset order for demos:

1. CRM
2. Incident
3. Workforce
4. Communication

The services are independent, so reset order does not enforce database foreign keys across services. This order mirrors the human workflow and keeps examples easier to reason about.

## Main Demo Flow Records

The strongest built-in demo path uses:

- `CUS-ALPHA`
- `INC-ALPHA-001`
- `SPEC-MAYA`
- `RES-MAYA-PENDING`
- `AR-PENDING-001`
- `NOT-EMAIL-DELIVERED`

The integration test creates additional `P6` resources on isolated temporary databases rather than mutating committed seed files.
