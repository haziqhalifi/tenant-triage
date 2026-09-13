# Mock private source pack

`data/mock-private-sources.json` is a synthetic placeholder dataset for the private records TenantTriage needs before it can operate beyond the current MVP.

It covers:

- maintenance SOP urgency rules, response targets, escalation contacts, spending approval limits, and access policy
- property and unit profiles for a fictional Sentul Residence workspace
- tenancy agreement clause summaries for repairs, tenant responsibilities, access, and notice-period routing
- appliance inventory with mock brands, models, serial numbers, warranty dates, and troubleshooting prompts
- approved contractor records with trades, coverage, hours, mock contacts, and approval thresholds
- maintenance-history enrichment with costs, invoice references, repair warranty notes, and recurrence notes
- public contractor candidates discovered with Exa but not approved

Every private name, phone number, email, agreement clause, vendor, serial number, invoice, and approval rule in the JSON file is mock data. Replace those values with verified records before using them in live operations.

The public utility URLs in the file point to official sources found with Exa:

- TNB contact: https://www.mytnb.com.my/contact-us
- TNB Guaranteed Service Levels: https://www.tnb.com.my/residential/gsl
- Air Selangor water updates: https://waterupdates.airselangor.com/
- IWK contact: https://www.iwk.com.my/contact-us

Suggested implementation path:

1. Load this file as a read-only reference layer in demo mode.
2. Add validation so live mode refuses records with `example.test`, `MOCK`, or `mock placeholder` values.
3. Replace JSON storage with SQLite tables if managers need to edit records from the dashboard.
4. Add a `source_registry` table with `last_verified_on` and `verified_by` before allowing contractor dispatch decisions.
