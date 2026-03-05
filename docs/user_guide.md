# User Guide

## Core Principle

- **One-time import** (Excel/CSV) is only used for initial data loading.
- After that, the **local database** is the **source of truth**.
- No cloud/bank synchronization.

## General UI Features

### Sorting (everywhere)
- Click on a column header: sorts ascending/descending (arrows ▲/▼)
- Double-click on a column header: reset sort order

### Scrolling (small monitors)
When the monitor is smaller than the displayed content:
- Each tab is embedded in a scroll area
- Scroll vertically and horizontally (scrollbars appear automatically)
- Mouse wheel: vertical; **Shift + Mouse wheel**: horizontal

## Overview

In the overview you can:
- Select a time period (**month** or **year**)
- View multiple tables/windows in parallel (incl. payout summary)
- See totals in fixed footers (remain visible while scrolling)

### 4th Window "Payout"
- Payout: beginning/mid
- Total: sum of income per payout period
- Savings: current savings share (according to rule)
- Debt: loan installments + (configured) variable/special expenses
- Fixed costs: recurring expenses
- Freely available: total minus deductions

## Income

### Fixed Salary
- Entries per month/year
- Default values (payout/account) come from the employer
- Filter by employer / payout / account

### Hourly Wage
- Entries per month/year
- "Recalculate" uses the employer's active surcharge rules
- BW/BY legacy values have been removed; only the neutral fields apply (Normal/Night/Sunday/Holiday/Overtime)

### Special Income
- Extra income (bonus, refund, gift, …)
- Assigned to month and account

### Employers & Surcharges
- Manage employers (name, payout timing, default account)
- Manage surcharges/rules per employer
- Rules can be historical (**valid from/to**); per rule type, the rule with the most recent `valid_from` takes precedence.

## Expenses

### Fixed Costs
- Recurring expenses: interval, due date, account, status
- **Interval > 1:** start month is displayed and requested when creating/editing
  - Interval 1: start month = "-"

### Variable Costs
- Monthly individual expenses (status, account, category)
- Button **"Paid"** marks the entry as paid
- Cancel instead of delete (status)

### Loans
- Loan list + monthly status
- Select a loan → events load automatically
- Event dialog is pre-filled (installment/timing/account), "just click & save" is possible
- Loan can be closed/reactivated

## Security

Menu **Security** (next to File):
- **Security mode…**: switch between
  - None
  - PIN
  - Device Security (Windows)
- **Change PIN…**: Re-key/re-encryption (SQLCipher)

Notes:
- If SQLCipher is not installed, a DPAPI fallback may be active for PIN/Device mode (not crash-safe).
- Once a DB is in SQLCipher format, the app requires SQLCipher to open it.
