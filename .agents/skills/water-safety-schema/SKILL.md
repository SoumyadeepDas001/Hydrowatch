---
name: water-safety-schema
description: Loads WHO/BIS water quality thresholds and source/village identifier formats for water reading analysis tasks.
---

# Water Safety Schema Guidelines

This skill defines the reference limits, schemas, and formatting rules for water quality monitoring within the HydroWatch system. Use these rules when parsing, validating, normalizing, and analyzing water quality readings.

## WHO & BIS Limits Reference

| Parameter | Standard / Guidance | Acceptable Limit | Permissible Limit | Action / Limit Trigger | Unit |
|---|---|---|---|---|---|
| **Fluoride** | WHO / BIS (IS 10500) | 1.0 mg/L | 1.5 mg/L | > 1.5 mg/L (Acute Breach) | mg/L |
| **Arsenic** | WHO / BIS (IS 10500) | 0.01 mg/L | 0.01 mg/L | > 0.01 mg/L (Acute Breach) | mg/L |
| **Turbidity** | WHO / BIS (IS 10500) | 1.0 NTU | 5.0 NTU | > 5.0 NTU (Acute Breach) | NTU |
| **Bacterial Counts** | WHO / BIS (IS 10500) | 0 CFU/100mL | 0 CFU/100mL | > 0 CFU/100mL (Acute Breach) | CFU/100mL |
| **pH** | WHO / BIS (IS 10500) | 6.5 | 8.5 | Outside [6.5, 8.5] (Acute Breach) | pH Units |

## Identifier Formatting Rules

*   **Village ID Format**: `VIL-[A-Z]{3}-[0-9]{3}`
    *   *Example*: `VIL-RAM-001` (Rampur), `VIL-SUN-002` (Sundarpur), `VIL-HAR-003` (Haripur)
*   **Source ID Format**: `SRC-[A-Z]{3}-[0-9]{4}`
    *   *Example*: `SRC-BOR-0003` (Borewell 3), `SRC-WEL-0005` (Open Well 5)

## Drift Trend Logic

A slow-drift scenario represents 3 or more consecutive readings steadily trending toward the threshold even if none have breached it yet.
*   **Formula**: Let $R_1, R_2, \ldots, R_n$ be a sequence of readings for the same parameter ordered chronologically. A drift is detected if there exists a subsequence of length $k \ge 3$ where:
    - $R_{i} < R_{i+1}$ (for increasing trend parameters like Fluoride, Arsenic, Turbidity, Bacterial Counts)
    - Or $R_{i} > R_{i+1}$ (for pH moving down towards acidic 6.5, or moving up towards alkaline 8.5)
    - AND the last reading in the sequence is within 25% of the safety limit.
