# Beeline tariff marketing campaigns requirements

This document summarizes the organizer-provided case, `HackAlem AI_ Beeline Tariff Marketing Campaigns Case.docx`. It is the implementation and submission checklist for the project. All case data and figures are synthetic and must not be presented as real Beeline business data or performance.

## Problem and user

The product is an agent for a marketing analyst planning next month's tariff migration campaigns. The agent must decide which subscribers to target, which tariff to offer, and which communication channel to use. It must use limited pilot campaigns to learn effects on the evaluation audience, then return a cost-aware final plan.

The business objective is to increase net revenue rather than maximize responses or gross ARPU uplift. Blind targeting can waste contact spend, produce no change, or cause a downsell.

Communication economics make broad untargeted campaigns impractical: spending the full 100,000-unit budget on calls would reach only 625 of the roughly 23,000 subscribers.

## Required agent behavior

Implement `agent.py` with an `Agent` class exposing:

```python
class Agent:
    def act(self, env) -> list[dict]:
        ...
```

The agent must:

- inspect the environment's customer profile, tariff and channel data, remaining resources, and pilot history;
- call `env.run_pilot(...)` at least once and use the observed results in its decisions;
- adapt to the evaluation effects rather than rely on constants tuned to the mock environment;
- return between 1 and 10 valid campaigns;
- stay within the simultaneous budget, contact, campaign-size, and pilot limits;
- finish within 10 minutes, including model calls;
- catch LLM or API failures and use a deterministic fallback so the run still completes.

Pilot design is a central part of the task. The case estimates that a 30-customer pilot incorrectly labels a moderately profitable segment as unprofitable about one time in four. At 200 customers, that happens about one time in 25, but the pilot costs roughly seven times as much. The case also states that a strategy without exploration earns about 15 times less than one that knows the true effects, so the agent should explicitly balance information quality against pilot cost.

Each final campaign chooses:

| Decision | Allowed values |
| --- | --- |
| Audience | A segment defined from subscriber ARPU, data use, call use, and/or current tariff |
| Offer | Any valid target tariff from `tariff_1` through `tariff_21` |
| Channel | `push`, `sms`, `digital_ads`, or `call` |

`target_tariff` and `channel` are required in each campaign dictionary. Audience filters are optional; omitting a filter means no restriction on that dimension. Supported examples in the case include `filter_arpu_segment`, `filter_data_segment`, and `filter_current_tariff`.

Example output shape:

```python
{
    "campaign_name": "Premium Upsell",
    "filter_arpu_segment": "HIGH",
    "filter_data_segment": "HEAVY",
    "filter_current_tariff": "tariff_4;tariff_8",
    "target_tariff": "tariff_10",
    "channel": "sms",
}
```

## Environment and data

The evaluation environment exposes at least:

- `env.customer_profile`: the campaign audience, 23,441 subscribers;
- `env.tariffs` and `env.channels`;
- `env.remaining_budget`, `env.remaining_contacts`, and `env.pilots_left`;
- `env.run_pilot(...)` for experiments on 10 to 200 subscribers;
- `env.pilot_history` with completed pilot results.

The case shows this pilot-call interface:

```python
env.run_pilot(
    target_tariff=...,
    channel=...,
    n_customers=...,
    filter_arpu_segment=...,
    filter_current_tariff=...,
)
```

The supplied environment is the authority for supported arguments. The case example documents ARPU and current-tariff filters for pilots even though final campaign dictionaries may include other optional audience filters such as `filter_data_segment`.

The participant package contains synthetic 2026 data:

| File | Contents |
| --- | --- |
| `customer_profile.csv` | Evaluation audience with current tariff, segments, behavior, and `predicted_arpu` |
| `data/change_tariff.csv` | History of 14,824 tariff changes with ARPU before and after |
| `data/traffic.csv` | Monthly minutes, SMS, data traffic, and device information |
| `data/arpu_monthly.csv` | Monthly subscriber revenue |
| `data/dict_tariff.csv` | Price and allowance data for 21 tariffs |
| `tariff_dictionary.csv` | Tariff descriptions |
| `feature_dictionary.csv` | Column descriptions |

The historical records describe a different subscriber sample from the evaluation audience. There is no supplied tariff-transition effect table; the agent must estimate useful hypotheses and learn evaluation effects through pilots.

Audience segments in `customer_profile.csv` are defined as follows:

| Field | Values | Definition |
| --- | --- | --- |
| `arpu_segment` | `LOW`, `MID`, `HIGH` | `ARPU_3m_avg` below 1,000; 1,000 to 5,000; above 5,000 |
| `data_segment` | `NON_USER`, `LITE`, `HEAVY` | 0 MB/month; above 0 through 2,000; above 2,000 |
| `call_segment` | `LOW`, `MEDIUM`, `HIGH` | below 100 minutes/month; 100 to 400; above 400 |

## Objective and scoring mechanics

The no-action baseline is 150,641,084 units, equal to the sum of `predicted_arpu`. A campaign's effect is a percentage of each targeted subscriber's ARPU, not a fixed amount.

The evaluated net result is:

```text
ARPU uplift for unique subscribers - communication cost
```

Pilot contacts and final-campaign contacts both count toward the result, budget, and contact limit. If campaigns overlap, each subscriber contributes once using the best campaign for that subscriber, while all attempted contacts still cost money.

| Channel | Cost per contact | Relative effectiveness |
| --- | ---: | ---: |
| `push` | 0 | 0.50 |
| `sms` | 4 | 0.65 |
| `digital_ads` | 22 | 0.85 |
| `call` | 160 | 1.20 |

## Hard constraints

All limits apply simultaneously:

- at most 10 final campaigns;
- at most 5,000 subscribers in any campaign; excess audience is not scored;
- at most 15,000 total contacts across pilots and final campaigns;
- at most 100,000 units of communication spend across pilots and final campaigns;
- at most 20 pilots;
- between 10 and 200 subscribers per pilot;
- each subscriber is credited at most once;
- no inspection of environment internals or organizer files outside the provided interface, including `__closure__`, garbage-collector inspection, or similar bypasses;
- no embedded secrets; read an LLM key from `os.environ["OPENAI_API_KEY"]` when needed.

If the agent crashes after running pilots, those pilot contacts and costs still count and the final result is negative. Failure handling must therefore cover the complete decision path, not only the LLM request itself.

## Required submission artifacts

| Artifact | Requirement |
| --- | --- |
| `agent.py` | Required; contains a runnable `Agent.act(env)` implementation |
| `submission.csv` | Required; reproducibly generated by `python make_submission.py` |
| `requirements.txt` | Required only when the solution needs additional libraries |
| `README.md` | Optional in the case specification, but scored under documentation and reproducibility |

The repository README must explain the solution, architecture, technologies, dependencies, environment variables, installation, execution, and a repeatable verification path. The general event rules require experts to be able to run the final project independently from the repository instructions.

## Acceptance checks

Before submission, run:

```bash
python local_eval.py
python local_eval.py --runs 10
python make_submission.py
```

The submission is acceptable when:

- `local_eval.py` completes and prints a result;
- it reports more than zero pilots;
- it shows no `Кампания ... отброшена` messages;
- the run does not exceed any resource limit;
- repeated runs remain reasonably stable rather than changing sign because of unlucky pilots;
- `submission.csv` exists and can be regenerated by the organizer's command.

The local evaluator uses mock effects. It validates mechanics and agent behavior, not the future judging score.

The participant package includes `agent_template.py` as a deliberately weak starting point. It is an interface example, not a performance target.

## Competitive opportunities

The case identifies these non-blocking advantages:

- quantify pilot uncertainty instead of comparing means alone;
- allocate pilot sizes and follow-up experiments adaptively;
- choose channels according to segment value and expected economics;
- remain robust to an unlucky sequence of pilot observations;
- use an LLM within the decision loop where it improves the agentic approach without compromising reliability.

## Technical evaluation rubric

| Criterion | Weight | Expected evidence |
| --- | ---: | --- |
| Task fit and functionality | 25 | The agent completes the required scenario and returns valid campaigns |
| Technical implementation | 25 | Sound architecture, decision logic, component interaction, and justified AI or agentic use |
| README and reproducibility | 25 | Clear design, setup, run, and verification instructions that work from the repository |
| Value and applicability | 15 | A practical response to the campaign-planning problem |
| Development potential and originality | 10 | Credible extensions, scale potential, or a well-founded original approach |
| **Total** | **100** | |

## Timing note

The case document's opening tagline mentions nine hours. The organizer's current general rules in `docs/updated_rules.md` define the official competitive development window as 13:00 to 18:00 on 23 September 2026, which is five hours. Treat the published event schedule as authoritative unless the organizers issue a case-specific clarification. The separate 10-minute limit applies to each agent evaluation run.
