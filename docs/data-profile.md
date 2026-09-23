# Beeline challenge data profile

## Scope and method

This profile covers the organizer-provided CSVs in `challenges/beeline-tariff-campaigns/`: the campaign audience, four files in `data/`, and the two dictionaries. It records row counts, field completeness, key uniqueness, date coverage, value ranges, tariff coverage, and subscriber-ID relationships. Checks were run read-only with pandas; no source data was changed.

All files describe synthetic challenge data. They are not actual Beeline customer records or business results. The package provides no freshness SLA or production-data contract, so timeliness is reported as date coverage rather than scored against an assumed freshness target.

## Inventory

| File | Rows × columns | Grain and role | Coverage / key notes |
| --- | ---: | --- | --- |
| `customer_profile.csv` | 23,441 × 29 | One campaign-audience row per `ID_NUMBER`; profile, segment fields, and `predicted_arpu` | IDs are unique and non-null. `predicted_arpu` sums to 150,641,084.25, matching the documented baseline. |
| `data/arpu_monthly.csv` | 78,798 × 3 | Monthly `ARPU_1M` observations by `ID_NUMBER` and `TIME_KEY` | Apr–Sep 2026; 14,991 IDs. There are 350 repeated ID-month keys (351 excess rows), including 84 exact duplicate excess rows and repeated keys with differing values. |
| `data/change_tariff.csv` | 14,823 × 6 | Tariff change events with pre/post three-month average ARPU | All rows dated 2026-10-01. There are 14,817 IDs and six exact duplicate excess rows. The guide says 14,824 changes, one more than the physical row count. |
| `data/traffic.csv` | 75,736 × 30 | Monthly subscriber usage and device observations by `ID_NUMBER` and `time_key` | Apr–Sep 2026; 14,875 IDs. No duplicate ID-month keys. `tariff_plan_code` is null on 16,725 rows (22.08%). |
| `data/dict_tariff.csv` | 21 × 5 | One tariff specification per `tariff_plan_code` | All 21 codes unique; no missing values. Prices range from 0 to 12,528.6 units. |
| `tariff_dictionary.csv` | 21 × 6 | Tariff specifications plus descriptions | All 21 codes unique; no missing values. |
| `feature_dictionary.csv` | 38 × 3 | Feature names, units, and descriptions | No missing values or duplicate rows. |

## Campaign audience profile

Segment coverage is:

| Field | Counts |
| --- | --- |
| `arpu_segment` | HIGH 13,918; MID 6,780; LOW 2,738; missing 5 |
| `data_segment` | HEAVY 11,735; LITE 10,253; NON_USER 1,343; missing 110 |
| `call_segment` | LOW 10,716; MEDIUM 8,309; HIGH 4,416; missing 0 |

There are 110 rows with at least one missing candidate filter among `current_tariff`, `arpu_segment`, and `data_segment`; `data_segment` is missing on all 110, `current_tariff` on 95, and `arpu_segment` on 5. The current `build_candidates` implementation drops rows missing any of these three fields. This is a safe treatment for filtered pilots, but means those 110 people are not targetable by its present candidate generator.

There are 481 audience rows with at least one missing field when optional behavior fields are included. For example, contact-history fields are missing on 470 rows and `COUNT_BASE_STATION` on 162. These optional fields should not be globally imputed as zero without evidence that missing means no activity.

After excluding rows with missing candidate filters, there are 23,331 usable rows across 168 non-empty current-tariff × ARPU × data-segment cells. Cell sizes are sparse: 66 cells have fewer than 10 subscribers, 24 have 10–19, and 78 have at least 20. No cell exceeds the 5,000-customer campaign cap. Candidate generation should keep its minimum-size rule and pilot sizes should use actual audience counts.

Numeric values are non-negative for `predicted_arpu` and `DATA_VOLUME`; the observed maxima are 216,619.82 and 425,742.18 respectively. `ARPU_current` and `ARPU_3m_avg` have long upper tails (maxima 1,417,082.91 and 476,043.63) and contain zero values. Without organizer-provided business bounds these are flagged for review, not treated as invalid. The segment definitions in the participant guide are based on `ARPU_3m_avg`, data use, and call use; preserve those documented bins rather than re-derive them from noisy extrema.

## Historical data and relationships

- The audience `ID_NUMBER` set has no overlap with the IDs in `change_tariff.csv`, `traffic.csv`, or `arpu_monthly.csv`. These history tables cannot be joined to the campaign audience at subscriber level. Use them only for aggregate priors or hypotheses; pilots are the available way to learn effects on the target audience.
- Every traffic ID and every tariff-change ID appears in the monthly ARPU table. The tariff-change and traffic tables overlap on 14,727 IDs; 90 change-history IDs have no traffic rows.
- All tariff codes referenced by non-null profile, history, and traffic tariff fields map to the 21-row tariff dictionary. The audience contains all 21 tariff codes; the traffic and change-history files cover fewer codes.
- The history has 168 observed ordered tariff pairs out of 420 possible pairs between distinct tariffs. Only 9 tariffs appear as a destination, so many candidate transitions have no direct historical support.
- `AVG_ARPU_PREV_3M` has one negative value (-37.41); `AVG_ARPU_NEXT_3M` has no negative values. Four monthly `ARPU_1M` values are negative (minimum -541.15). These are anomalies to inspect before ratios or averages; the source files are preserved, and the participant data does not define whether negative ARPU is valid.
- `arpu_monthly.csv` repeats 350 subscriber-month keys. Since 84 excess rows are exact duplicates and the other repeated keys include differing values, an aggregate should not silently sum or average this table as if each key were unique. Establish an explicit deduplication or aggregation rule first. The present agent does not consume this file.
- `change_tariff.csv` has six exact duplicate excess rows across six repeated subscriber-event keys. Exact-deduplicate for exploratory transition counts and estimates to avoid giving those events extra weight. The source file remains unchanged. Its physical row count (14,823) is one below the guide's stated count; the unique event count after removing exact duplicates is 14,817.
- `traffic.csv` has no repeated subscriber-month keys, but the 22.08% missing tariff field limits tariff-specific usage analysis. Usage fields can still be analyzed by subscriber and month where present; do not fill missing tariff codes from the campaign audience because the IDs do not overlap.

## Data-quality findings

| Dimension | Finding | Severity for current agent | Handling |
| --- | --- | --- | --- |
| Completeness | 110 audience rows lack at least one required candidate filter; optional behavior fields have more missingness. | Medium | Continue excluding incomplete filtered cells. Do not treat optional nulls as zeros without a documented meaning. |
| Uniqueness | 350 repeated ID-month keys in monthly ARPU; six exact duplicate excess rows in tariff-change history. | High for analyses using those tables | Resolve monthly duplicate keys before aggregation; exact-deduplicate change rows for transition statistics. Keep organizer sources unchanged. |
| Consistency | Audience IDs are disjoint from historical IDs; historical transition coverage is sparse. | High for subscriber-level inference; low for aggregate prior use | Do not claim person-level joins. Track transition support counts and rely on pilots for current-audience effects. |
| Validity / accuracy | Negative ARPU values and extreme upper tails exist; authoritative bounds are absent. | Medium for derived ratios | Inspect and report; avoid automatic clipping or deletion absent a case rule. |
| Timeliness | Monthly files cover Apr–Sep 2026 and changes are dated Oct 1, 2026. | Not scored | No freshness SLA is supplied; dates align with the synthetic challenge timeline. |
| Referential integrity | All observed non-null tariff codes map to the tariff dictionary. | Pass | Retain validation when constructing candidate offers. |

## Implications for the agent and next analysis

The current workflow uses `customer_profile.csv`, `dict_tariff.csv`, and `change_tariff.csv`. It does not use `traffic.csv` or `arpu_monthly.csv`. Candidate ranking should treat historical transition estimates as weak, sparse priors and retain their support counts. Do not join the history onto audience rows by `ID_NUMBER`.

Before using the monthly files to improve candidate hypotheses, resolve the repeated subscriber-month ARPU keys, inspect the negative ARPU entries, and decide whether missing tariff values make a proposed traffic analysis too incomplete. Then summarize historical transition outcomes by source tariff, destination tariff, and the documented ARPU bands with exact duplicate history rows removed and support counts shown. Validate any campaign decision against pilots, not historical aggregate outcomes alone.

## Limitations

This is a structural and campaign-relevance profile, not an audit against a production SLA. No external source of truth, approved numeric bounds, or expected row counts beyond the participant guide was supplied. The data is synthetic, and local evaluator effects are mock effects; neither this profile nor any derived campaign recommendation represents real Beeline customer behavior or business performance.
