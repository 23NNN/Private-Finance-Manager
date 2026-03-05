# Data Model

## Core Tables (excerpt)

- `account`
- `employer`
- `pay_rule` (surcharges/rules, incl. `valid_from/valid_to`)
- `income_fixed`
- `income_hourly`
- `income_special`
- `expense_category` (grouping FIX/VARIABLE/LOAN)
- `expense_recurring`
- `expense_variable`
- `loan`
- `loan_event`
- `savings_rule`, `savings_goal`, `savings_contribution`
- `import_run`

## Income

### income_fixed
- per employer/month/year
- `base_amount`, `special_amount`, `calc_amount`, `actual_amount`
- `payout_timing` (beginning/mid)
- `account_id`

### income_hourly
- per employer/month/year
- Hour fields (neutral): `hours_normal`, `night`, `sunday`, `holiday`, `overtime`
- Legacy BW/BY fields were migrated to 0 and are no longer used
- `special_amount`, `calc_amount`, `actual_amount`
- `payout_timing`, `account_id`

### income_special
- Special income: `name`, `amount`, `actual_amount`, `year/month`, `payout_timing`, `account_id`

## Expenses

### expense_recurring (fixed costs)
- `amount`
- `frequency_months` (interval)
- `due_day`
- `anchor_month` (start month)
  - Required when `frequency_months > 1`
  - When `frequency_months == 1` typically `NULL`
- `pay_bucket` (beginning/mid)
- `account_id`, `status`

### expense_variable
- Individual expenses: `amount`, `year/month`
- `status` (PAID/CANCELLED/…)
- `pay_bucket`, `account_id`, `category_id`

## Loans

### loan
- `regular_payment`, `payment_timing`, `account_id`, `status`

### loan_event
- Types: payment, special repayment, rate change, …
- Overrides (account/timing) are serialized into Notes if needed (marker), keeping migrations lean.

## Savings

### savings_rule
- per employer (historically via `valid_from/valid_to`)
- `percentage` (UI: min 10%, max 35%)

## Migrations

- Alembic versions under `src/infrastructure/db/migrations/versions/`
- The app runs `upgrade_db_if_possible()` on startup.
- Additionally, `schema_patch.py` exists as a best-effort supplement in the MVP.

