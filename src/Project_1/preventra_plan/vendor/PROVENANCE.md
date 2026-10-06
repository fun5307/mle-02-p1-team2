# Reused teammate modules

Copied byte-for-byte from the user-provided source on 2026-10-06. Originals remain untouched.

- `work_plan.py`: `src_v2/shining_chatbot/work_plan.py`; SHA-256 `cc47229ad0b1b4b918aefd4f0514021d15191beb70a2e2b41be3560f8bd2101f`
- `business_time.py`: `src_v2/shining_chatbot/business_time.py`; SHA-256 `d2bf42f0d7d8a8b56e8f40510972e5d51b174bbb97c29fd270bbe8226bbacf71`

## Administrator report adaptation (2026-10-06)

- `../report.py::timeline_html` adapts minute offsets, duration bars and overlap emphasis from
  `src_v2/shining_chatbot/field_dashboard.py::_timeline` (555–601); scoped HTML replaces the original global CSS.
- Report organization follows `briefing_report.py::safety_briefing_html` and the daily dashboard.
  Plan controls, missing fields and overlap checks reuse the copied parser helpers.
- The teammate's `case_summary.py` depends on `source_01_sif_cases.parquet`, absent in the supplied repository.
  Related candidates therefore use existing Preventra `search_sif_cases`, with existing Langfuse tracing.
  Candidate counts are explicitly not archive totals, probabilities or risk scores. Type charts require an
  explicit source type field; absent classifications are not inferred from narrative text.
- Sidebar metadata is queried from existing scoped conversation/plan tables. Site names group uploads;
  dates select the latest stored plan containing that date. Earlier conversations stay accessible inside
  the site group. Date selection retains that plan conversation's existing chat history.
