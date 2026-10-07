# Check results

| Case | Question | Expected | Observed | Result |
| ---- | -------- | -------- | -------- | ------ |
| C1 Draft with a citation | Q3 | status=draft; citations=[SUPPORT-v1:p1]; answer_contains=[09:00, 17:00, UTC]; warning_kinds=[] | status=draft; citations=[SUPPORT-v1:p1]; answer_contains=[09:00, 17:00, UTC]; warning_kinds=[] | PASS |
| C2 Undocumented feature is unresolved | Q2 | status=unresolved; owner=Product reviewer; citations=[]; allowed_actions=[leave_open] | status=unresolved; owner=Product reviewer; citations=[]; allowed_actions=[leave_open] | PASS |
| C3 Older version conflicts | Q1 | status=draft; citations=[EXPORT-v2:p1]; replaced=[EXPORT-v1:p1]; warning_kinds=[superseded]; answer_starts_with=No | status=draft; citations=[EXPORT-v2:p1]; replaced=[EXPORT-v1:p1]; warning_kinds=[superseded]; answer_starts_with=No | PASS |
| C4 Approved answer is reused | Q1 | after_edit={status=draft; approved=False}; after_approve={status=approved; answer_is_edit=True}; ask_again_new_model_calls=0 | after_edit={status=draft; approved=False}; after_approve={status=approved; answer_is_edit=True}; ask_again_new_model_calls=0 | PASS |
| C5 Changed source needs review | Q1 | after_restart={status=approved; citations=[EXPORT-v2:p1]}; after_bump={status=needs_review; new_model_calls=0; warning_kinds_include=[source_changed]}; after_reapprove={source_versions={EXPORT-v2=3}} | after_restart={status=approved; citations=[EXPORT-v2:p1]}; after_bump={status=needs_review; new_model_calls=0; warning_kinds_include=[source_changed]}; after_reapprove={source_versions={EXPORT-v2=3}} | PASS |
| C6 Model failure shows as an error | Q9 | status=error; error=Model call failed: timeout.; label=simulated; allowed_actions=[retry]; after_run_all={q3_status=draft} | status=error; error=Model call failed: timeout.; label=simulated; allowed_actions=[retry]; after_run_all={q3_status=draft} | PASS |

## Failures

None.
