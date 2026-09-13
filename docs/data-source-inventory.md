# TenantTriage data source inventory

This inventory maps the maintenance-agent knowledge sources to what is already available in this workspace and what still needs to be provided or connected before the agent can use it operationally.

| Document or data | What the agent uses it for | Current source or gap | Recommended next step |
| --- | --- | --- | --- |
| Maintenance SOP | Urgency levels, response targets, escalation contacts, spending approval limits | Partial. `README.md` documents SOP v1 response targets: low/medium 48 hours, high 2 hours, crisis immediate attention. `engine.py` applies those targets. Escalation contacts and spending limits are not present. | Create a property-specific SOP file with urgency definitions, response targets, manager escalation contacts, emergency handling, and approval limits. |
| Property and unit profiles | Address, installed appliances, model numbers, warranties, building management contacts | Partial. `.env`/`config.py` supports `PROPERTY_NAME`, `UNIT_ID`, and `TENANT_NAME`; default demo values are `Sentul Residence` and `B-12-03`. No appliance inventory, warranties, or verified building management contacts are stored. | Add a structured property/unit profile table or JSON file. Include address, building/JMB contacts, appliance brand/model/serial, warranty dates, and access notes. |
| Tenancy agreements | Retrieve relevant repair, access, responsibility, and notice clauses for manager review | Not present. The README says lease/legal inquiries are handed to the manager and no lease RAG or notice drafting is implemented. | Store signed agreements in a private document store. Index only clauses needed for manager review and require human approval before any legal-facing response. |
| Approved contractor directory | Match issues to plumbers, electricians, AC technicians; know coverage and hours | Not present. The app currently uses fictional local inspection slots and does not dispatch contractors. | Add an approved vendor directory with trade, service area, hours, emergency status, contact route, license/insurance notes, and spending thresholds. |
| Maintenance history | Recognise recurring faults, previous repairs, costs, and unresolved issues | Partial. SQLite stores tickets, messages, case notes, actions, and local scheduling in `data/live.sqlite3` and `data/demo.sqlite3`. Costs and invoice links are not stored. | Continue using tickets/messages/notes for issue history. Add invoice/vendor/cost fields if recurring-fault and spend analysis are required. |
| Appliance manuals | Explain error codes and retrieve manufacturer guidance for the exact model | Not present. Needs appliance brand and model numbers first. | Use Exa or direct manufacturer sites after collecting model numbers. Store the official manual URL and key troubleshooting pages in the unit profile. |
| Building and utility guidance | Find reporting procedures, official service contacts, and public notices | Partially discoverable from public official sources. Utility sources found: TNB, Air Selangor, IWK. Building management contact for the exact property still needs verification. | Use official utility pages for general guidance. Verify building/JMB/management contacts from owner records, resident app, notice board, or management office. |
| Potential contractors | Research additional providers by location and service | Public candidates found for Sentul/Kuala Lumpur, but none are approved. | Use public vendor websites only as candidates. Verify credentials, pricing, insurance, service hours, and manager approval before adding to the approved directory. |

## Public sources found with Exa

I reviewed 28 Exa results across four search passes on 2026-09-13.

| Source | URL | Use | Notes |
| --- | --- | --- | --- |
| Sentul Residence official website | https://www.sentulresidence.com/ | Candidate property-management source | Public site references property rental and property management services. Verify this is the correct operational contact for the unit before use. |
| TNB contact page | https://www.mytnb.com.my/contact-us | Electricity outage reporting | Official TNB source for outage reporting and CareLine details. |
| TNB Guaranteed Service Levels | https://www.tnb.com.my/residential/gsl | Electricity restoration/service-level guidance | Official TNB source for GSL/MSL targets and rebate context. |
| Suruhanjaya Tenaga complaint process | https://www.st.gov.my/contact-us/feedback-and-complaint/how-to-lodge | Escalating electricity supply complaints | Official regulator source for complaint process and consumer rights. |
| Air Selangor contact page | https://www.airselangor.com/contact-us | Water-service contact | Official water utility contact page. |
| Air Selangor Water Updates | https://waterupdates.airselangor.com/ | Current water disruption notices | Official water disruption status page. |
| Air Selangor water info | https://www.airselangor.com/whats-happening/water-info | Water guidance and notices | Official water information source. |
| IWK contact page | https://www.iwk.com.my/contact-us | Sewerage contact and Kuala Lumpur operational office | Official IWK contact source. |
| IWK sewerage FAQ | https://customerportal.iwk.com.my/en/faq/iwk_sewerage_services | Distinguishing public sewer responsibilities from private internal blockages | Official customer portal guidance. |
| IWK customer charter | https://www.iwk.com.my/customer-charter | Sewerage service response expectations | Official IWK service charter. |

## Public contractor candidates found with Exa

These are candidate vendors only. They should not be treated as approved contractors until verified by the property manager.

| Vendor candidate | URL | Claimed service fit |
| --- | --- | --- |
| Mr. Fix Sentul | https://mrfixenterprise.com/sentul/ | Plumbing, electrical, air-conditioning |
| Empire Plumber Sentul | https://sentul.empireplumber.com.my/ | 24/7 plumbing |
| First Electrician Sentul | https://sentul.firstelectrician.com.my/ | 24/7 electrical |
| AirconBro Sentul | https://airconbro.com/sentul/ | Air-conditioning service and repair |
| A PRO PLUMBER Malaysia | https://www.aproplumber.com.my/ | Plumbing, electrical, air-conditioning |
| AlphaWater Plumbing Sentul | https://awplumbing.my/plumbing-service-in-sentul/ | Plumbing |
| Mr Plumber Sentul | https://www.mrplumber.my/area-coverage/sentul/ | Plumbing |
| ShanBro | https://www.shanbroelectrician.com/ | Electrical and plumbing |
| KL Plumber & Electrician Services | https://klplumberelectricianservices.com/services/ | Plumbing and electrical |
| Aim Electric & Plumbing Service | https://aimelectricpower.com/ | Electrical, plumbing, home maintenance |

## Data model gaps to add

- `maintenance_sop`: urgency definitions, target response time, escalation contact, tenant message template, spending limit, approval requirement.
- `properties`: property name, full address, building management/JMB contacts, resident app/notice-board source, utility area.
- `units`: unit id, tenant id, appliance inventory, warranty records, access constraints.
- `appliances`: brand, model, serial number, install date, manual URL, warranty expiry, common error-code references.
- `contractors`: vendor name, trade, coverage area, hours, emergency availability, contact method, approval status, insurance/license notes.
- `repair_costs` or `invoices`: ticket id, contractor id, date, line items, total, invoice file/link, warranty on repair.
- `source_registry`: source type, URL/file path, owner, last verified date, verification status.
