"""Optional, bounded LLM choice among Python-validated pilot hypotheses.

Only aggregate synthetic challenge data and prior pilot observations are sent.
The model never chooses filters, contact counts, channels, or campaign budgets.
"""

import json
import os
from typing import Optional, Sequence, Tuple
from urllib.request import Request, urlopen

from campaign_planner import Belief

DEFAULT_MODEL = "gpt-4o-mini"
RESPONSES_URL = "https://api.openai.com/v1/responses"


def select_pilot(
    shortlist: Sequence[Tuple[Belief, float]],
    pilot_results: Sequence[dict],
    transport=urlopen,
) -> Optional[Belief]:
    """Return a listed hypothesis, or None so the deterministic policy wins."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not shortlist or not api_key:
        return None

    choices = {f"candidate_{i}": belief for i, (belief, _) in enumerate(shortlist)}
    candidates = [
        {
            "id": f"candidate_{i}",
            "current_tariff": belief.hypothesis.cell.current_tariff,
            "arpu_segment": belief.hypothesis.cell.arpu_segment,
            "target_tariff": belief.hypothesis.target_tariff,
            "audience_size": belief.hypothesis.cell.size,
            "audience_predicted_arpu_sum": round(belief.hypothesis.cell.arpu_sum, 2),
            "estimated_base_lift_ratio": round(belief.mean, 5),
            "uncertainty_sd": round(belief.sd, 5),
            "previous_pilots": belief.pilots,
            "knowledge_gradient": round(score, 2),
        }
        for i, (belief, score) in enumerate(shortlist)
    ]
    schema = {
        "type": "object",
        "properties": {"candidate_id": {"type": "string", "enum": list(choices)}},
        "required": ["candidate_id"],
        "additionalProperties": False,
    }
    prompt = (
        "Choose exactly one candidate ID for the next tariff-campaign pilot. "
        "Use only the supplied aggregate estimates and observed pilot results. "
        "Balance possible decision improvement, audience value, uncertainty, "
        "and what previous pilots have already taught us. Do not invent effects "
        "or request any other action. Return only the structured choice.\n"
        + json.dumps({"candidates": candidates, "completed_pilots": list(pilot_results)})
    )

    payload = {
        "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pilot_choice",
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = Request(
        RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with transport(request, timeout=15.0) as connection:
            response = json.load(connection)
        if response.get("status") != "completed":
            return None
        output_text = "".join(
            content["text"]
            for item in response["output"]
            if item.get("type") == "message"
            for content in item.get("content", [])
            if content.get("type") == "output_text"
        )
        selected_id = json.loads(output_text)["candidate_id"]
    except Exception:  # network, timeout, refusal, or malformed API response
        return None
    return choices.get(selected_id)
