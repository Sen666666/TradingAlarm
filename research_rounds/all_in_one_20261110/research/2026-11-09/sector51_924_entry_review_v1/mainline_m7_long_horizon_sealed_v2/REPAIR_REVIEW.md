# Isolated non-economic admission repair

Original design and completed v6 outputs remain untouched. This wrapper adds a hash-bound baseline manifest and exact required family inventory. It independently verifies original OUTPUT_HASHES contents and all actual export SHA256 values, status and audit. Missing or unexpected baseline/checkpoint JSON families cannot silently pass. Original economic methods, next-day terminal guard, atomic loop and October31/final-only export schedule are unchanged. June30 is still a ceiling, not a completion promise. No historical run or approval is created here.

Compared families (33):
- ADD_FLOOR_RISK
- ALL_TARGETS_BLOCKER_SCAN
- ATTEMPTS
- AVAILABILITY_EVENTS
- BLOCKERS
- CANDIDATES
- CAPITAL_LOTS
- CP_EVENTS
- CURRENT_EVENT
- DAY_LEDGER
- EQUITY_EVENTS
- EVENT_LOG
- EVENT_REGISTRY
- EVENT_REQUEST_PLANS
- EXCLUDED_UNCLASSIFIED
- FUNDING_REQUESTS
- HOLDINGS
- INFORMATION_CONFIRMATIONS
- OPEN_SECTOR_EXPOSURE
- ORDERS
- PENDING_AT_END
- QUOTE_GAPS
- REFERENCE_AT_END
- REFERENCE_DAILY
- REFERENCE_REQUESTS
- RETRY_TICKETS
- SECTOR_DAILY
- SEED_COMMISSION_DIAGNOSTIC
- SEED_FLOOR_RISK
- TICKET_STATE
- TRANSFERS
- TRANSFER_PLAN_AT_END
- UNCERTIFIED_DAY

Inventory-only exclusions (3):
- EVENT_ADMISSION
- OUTPUT_HASHES
- SOURCE_HASHES
