# Member 2 API Samples

These examples use Windows PowerShell and placeholders for local credentials.

```powershell
$toolToken = "<your-local-tool-token>"
$adminKey = "<your-local-admin-key>"
$requestId = [guid]::NewGuid().ToString()
$headers = @{
  "X-Tool-Token" = $toolToken
  "X-Request-ID" = $requestId
}
$adminHeaders = @{
  "X-Admin-Key" = $adminKey
  "X-Request-ID" = $requestId
}
```

## CRM

Health:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8101/health" -Headers @{ "X-Request-ID" = $requestId }
```

Readiness:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8101/readiness" -Headers @{ "X-Request-ID" = $requestId }
```

List customers:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8101/crm/api/v1/customers?page=1&page_size=20&tier=Enterprise" -Headers $headers
```

Get customer:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8101/crm/api/v1/customers/CUS-ALPHA" -Headers $headers
```

Create customer:

```powershell
$body = @{
  customer_id = "CUS-DEMO-001"
  name = "Demo Manufacturing"
  tier = "Enterprise"
  arr = "275000.00"
  renewal_date = "2099-11-15"
  active = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8101/crm/api/v1/customers" -Headers $headers -ContentType "application/json" -Body $body
```

Update customer:

```powershell
$body = @{
  name = "Demo Manufacturing Group"
  tier = "Premium"
  arr = "300000.00"
  renewal_date = "2099-12-01"
  active = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Put -Uri "http://localhost:8101/crm/api/v1/customers/CUS-DEMO-001" -Headers $headers -ContentType "application/json" -Body $body
```

Reset CRM:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8101/admin/reset" -Headers $adminHeaders
```

## Incident

Create incident:

```powershell
$body = @{
  incident_id = "INC-DEMO-001"
  customer_id = "CUS-ALPHA"
  title = "Checkout latency spike"
  description = "Checkout latency exceeded normal operating thresholds."
  priority = "high"
  sla_deadline = "2099-08-01T10:00:00Z"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8102/incident/api/v1/incidents" -Headers $headers -ContentType "application/json" -Body $body
```

List incidents:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8102/incident/api/v1/incidents?page=1&page_size=20" -Headers $headers
```

Filter incidents:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8102/incident/api/v1/incidents?priority=CRITICAL&unassigned=true&overdue=true" -Headers $headers
```

Get incident:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8102/incident/api/v1/incidents/INC-DEMO-001" -Headers $headers
```

Update status:

```powershell
$body = @{ status = "IN_PROGRESS" } | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "http://localhost:8102/incident/api/v1/incidents/INC-DEMO-001/status" -Headers $headers -ContentType "application/json" -Body $body
```

Assign specialist:

```powershell
$body = @{ specialist_id = "SPEC-MAYA" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8102/incident/api/v1/incidents/INC-DEMO-001/assign" -Headers $headers -ContentType "application/json" -Body $body
```

Reset Incident:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8102/admin/reset" -Headers $adminHeaders
```

## Workforce

List specialists:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8103/workforce/api/v1/specialists?page=1&page_size=20" -Headers $headers
```

List available specialists:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8103/workforce/api/v1/specialists/available?skill=technical&required_capacity=1" -Headers $headers
```

Get specialist:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8103/workforce/api/v1/specialists/SPEC-MAYA" -Headers $headers
```

Create reservation:

```powershell
$body = @{
  reservation_id = "RES-DEMO-001"
  specialist_id = "SPEC-MAYA"
  incident_id = "INC-DEMO-001"
  expires_in_seconds = 300
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8103/workforce/api/v1/reservations" -Headers $headers -ContentType "application/json" -Body $body
```

Get reservation:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8103/workforce/api/v1/reservations/RES-DEMO-001" -Headers $headers
```

Confirm reservation:

```powershell
Invoke-RestMethod -Method Patch -Uri "http://localhost:8103/workforce/api/v1/reservations/RES-DEMO-001/confirm" -Headers $headers
```

Cancel or release reservation:

```powershell
Invoke-RestMethod -Method Delete -Uri "http://localhost:8103/workforce/api/v1/reservations/RES-DEMO-001" -Headers $headers
```

Reset Workforce:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8103/admin/reset" -Headers $adminHeaders
```

## Communication

Create assignment request:

```powershell
$body = @{
  request_id = "AR-DEMO-001"
  incident_id = "INC-DEMO-001"
  specialist_id = "SPEC-MAYA"
  message = "Please review and accept this incident assignment."
  expires_in_seconds = 900
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8104/communication/api/v1/assignment-requests" -Headers $headers -ContentType "application/json" -Body $body
```

List requests:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8104/communication/api/v1/assignment-requests?pending_only=true" -Headers $headers
```

Get request:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8104/communication/api/v1/assignment-requests/AR-DEMO-001" -Headers $headers
```

Accept request:

```powershell
$body = @{
  response = "ACCEPTED"
  response_note = "I can take this incident now."
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8104/communication/api/v1/assignment-requests/AR-DEMO-001/respond" -Headers $headers -ContentType "application/json" -Body $body
```

Reject request:

```powershell
$body = @{
  response = "REJECTED"
  response_note = "Capacity is already committed."
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8104/communication/api/v1/assignment-requests/AR-SECOND-DEMO/respond" -Headers $headers -ContentType "application/json" -Body $body
```

Create notification:

```powershell
$body = @{
  notification_id = "NOT-DEMO-001"
  recipient = "maya.sen@example.test"
  channel = "EMAIL"
  subject = "New Incident Assignment"
  message = "You have received assignment request AR-DEMO-001."
  related_request_id = "AR-DEMO-001"
  idempotency_key = "assignment-ar-demo-001-email"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8104/communication/api/v1/notifications" -Headers $headers -ContentType "application/json" -Body $body
```

List notifications:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8104/communication/api/v1/notifications?status=DELIVERED" -Headers $headers
```

Get notification:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8104/communication/api/v1/notifications/NOT-DEMO-001" -Headers $headers
```

Reset Communication:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8104/admin/reset" -Headers $adminHeaders
```
