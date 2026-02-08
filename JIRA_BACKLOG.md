# 📋 Jira Backlog - Web Health Monitor (WHMD)

This backlog tracks user stories, tasks, and system enhancements using Agile Scrum/Kanban methodologies.

---

## 🚀 Active Sprint (Sprint 1)

### [WHMD-101] Feature: Recent URLs & Search History
**User Story:**
> **As a** Dashboard User,
> **I want** to see my recently monitored URLs in the search field,
> **So that** I can quickly re-check them without re-typing.

**Acceptance Criteria:**
- [ ] Save the last 5 searched URLs in `localStorage`.
- [ ] Display a dropdown/list of suggestions when focusing the search input.
- [ ] Clicking a suggestion populates the input and triggers focus.
- [ ] Option to clear history.

**Status:** ✅ Done <!-- id: WHMD-101 -->

---

### [WHMD-102] Improvement: Dashboard Stats Dashboard Summary
**User Story:**
> **As an** Admin,
> **I want** a summary card showing "Average Response Time" and "Uptime Percentage",
> **So that** I can judge the overall health at a glance.

**Acceptance Criteria:**
- [ ] Calculate global average response time from all `CheckResult` entries.
- [ ] Calculate uptime percentage (Up / Total Checks).
- [ ] Display in premium-styled cards above the monitor grid.

**Status:** ✅ Done <!-- id: WHMD-102 -->

---

### [WHMD-107] Feature: Data Export (CSV/JSON)
**User Story:**
> **As a** Dashboard User,
> **I want** to export my audit data to CSV or JSON,
> **So that** I can analyze results in external tools or keep backups.

**Acceptance Criteria:**
- [x] Add "Export JSON" button to Dashboard.
- [x] Add "Export CSV" button to Dashboard.
- [x] Generate file client-side using current monitor list data.

**Status:** ✅ Done <!-- id: WHMD-107 -->

## 📥 Product Backlog (Unscheduled)

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| WHMD-103 | Alerting: Email Notifications on Failure | High | Backlog |
| WHMD-104 | UI: Export Weekly PDF Report | Medium | Backlog |
| WHMD-105 | Security: Account Password Complexity Rules | Low | Backlog |
| WHMD-106 | Mobile: Improve PWA manifest and icons | Medium | Backlog |

---

## ✅ Completed Issues
- **[WHMD-101]** Feature: Recent URLs & Search History - *Status: Done* ✅
- **[WHMD-102]** Improvement: Dashboard Stats Summary - *Status: Done* ✅
- **[WHMD-107]** Feature: Data Export (CSV/JSON) - *Status: Done* ✅
