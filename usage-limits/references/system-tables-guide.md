# System Tables Reference

## system.ai_gateway.usage (Preferred)

- **Retention**: 365 days
- **Access**: Account admin or granted via `GRANT SELECT`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `requester` | STRING | User email who made the request |
| `requester_type` | STRING | "USER" or "SERVICE_PRINCIPAL" |
| `endpoint_name` | STRING | Serving endpoint name |
| `event_time` | TIMESTAMP | Request timestamp |
| `input_tokens` | BIGINT | Input token count |
| `output_tokens` | BIGINT | Output token count |
| `total_tokens` | BIGINT | Total token count |
| `destination_model` | STRING | Model name (e.g., "claude-sonnet-4-20250514") |

## system.serving.endpoint_usage (Fallback)

- **Retention**: 90 days
- **Access**: Account admin or granted via `GRANT SELECT`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `requester` | STRING | User email |
| `request_time` | TIMESTAMP | Request timestamp |
| `input_token_count` | BIGINT | Input token count (estimated if not returned by model) |
| `output_token_count` | BIGINT | Output token count (estimated) |

### Token Estimation Note

When the model doesn't return explicit token counts, Databricks estimates using:
`token_count = (text_length + 1) / 4`

## Granting Access

```sql
-- Grant to a service principal
GRANT SELECT ON TABLE system.ai_gateway.usage TO `my-app-principal`;
GRANT SELECT ON TABLE system.serving.endpoint_usage TO `my-app-principal`;
```
