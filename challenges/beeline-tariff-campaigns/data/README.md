# Organizer input data

Preserve these original filenames and schemas. All supplied data is synthetic.
Paths below are relative to the challenge directory, one level above this file.

| Path | Used by | Purpose |
|---|---|---|
| `customer_profile.csv` | Local environment | Audience table; the agent receives it as `env.customer_profile` |
| `data/dict_tariff.csv` | Local environment | Tariff catalog; the agent receives it as `env.tariffs` |
| `data/change_tariff.csv` | Agent and local evaluator | Historical prior for the agent; also used to construct the local mock effects |
| `data/traffic.csv` | Optional participant research | Usage history; not read by the final agent |
| `data/arpu_monthly.csv` | Optional participant research | Monthly revenue history; not read by the final agent |
| `tariff_dictionary.csv` | Participant reference | Tariff descriptions; not read by the final agent |
| `feature_dictionary.csv` | Participant reference | Column descriptions; not read by the final agent |

At judging time, audience and catalog tables come through `env`. The guide says
judging effects differ from the mock; their observations are obtained through
pilots. The agent must not read hidden judging effect files.

Changing folder names is not required to accept different data. Replacement local
inputs should use the same paths and schemas. Changing history changes both the
agent's prior and the local mock; it is not a test of hidden judging performance.

Team-generated history summaries are in `../experiments/prepared_history/`,
separate from these source files. Artificial effect tables and experiment outputs
also stay under `../experiments/`. The final agent reads none of those artifacts.
