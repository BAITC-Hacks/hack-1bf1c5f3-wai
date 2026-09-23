"""Offline checks for the optional LLM decision boundary."""

import json
import os
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from agent import Agent
from campaign_planner import Belief
from candidate_research import Cell, Hypothesis
from llm_selector import select_pilot
from mock_environment import make_mock_env


def _shortlist():
    cell = Cell("tariff_1", "MID", 120, 240_000.0)
    first = Belief(Hypothesis(cell, "tariff_2", 0.1, 0.15))
    second = Belief(Hypothesis(cell, "tariff_3", 0.08, 0.15))
    return [(first, 400.0), (second, 350.0)]


class LlmSelectorTests(unittest.TestCase):
    @staticmethod
    def _response(candidate_id):
        return BytesIO(json.dumps({
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({"candidate_id": candidate_id}),
                }],
            }],
        }).encode("utf-8"))

    def test_accepts_only_a_listed_choice(self):
        transport = Mock(return_value=self._response("candidate_1"))
        shortlist = _shortlist()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}):
            selected = select_pilot(shortlist, [], transport=transport)

        self.assertIs(selected, shortlist[1][0])
        request = transport.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(
            payload["text"]["format"]["schema"]["properties"]["candidate_id"]["enum"],
            ["candidate_0", "candidate_1"],
        )
        self.assertNotIn("ID_NUMBER", payload["input"])
        self.assertEqual(transport.call_args.kwargs["timeout"], 45.0)

    def test_timeout_is_configurable_and_bounded(self):
        transport = Mock(return_value=self._response("candidate_0"))
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-only-placeholder",
            "OPENAI_SELECTOR_TIMEOUT": "120",
        }):
            select_pilot(_shortlist(), [], transport=transport)
        self.assertEqual(transport.call_args.kwargs["timeout"], 90.0)

    def test_invalid_choice_or_api_failure_falls_back(self):
        transport = Mock(return_value=self._response("candidate_99"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}):
            self.assertIsNone(select_pilot(_shortlist(), [], transport=transport))
            transport.side_effect = TimeoutError("API unavailable")
            self.assertIsNone(select_pilot(_shortlist(), [], transport=transport))

    def test_no_key_skips_the_api(self):
        transport = Mock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertIsNone(select_pilot(_shortlist(), [], transport=transport))
        transport.assert_not_called()

    def test_agent_uses_at_most_four_model_checkpoints(self):
        env, _ = make_mock_env(seed=42)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}):
            with patch("agent.select_pilot", side_effect=lambda ranked, _: ranked[-1][0]) as choose:
                with patch("builtins.print"):
                    campaigns = Agent().act(env)

        self.assertEqual(choose.call_count, 4)
        self.assertEqual(len(env.pilot_history), 20)
        self.assertGreaterEqual(len(campaigns), 1)
        self.assertLessEqual(len(campaigns), 10)

    def test_agent_disables_ai_after_an_api_failure(self):
        env, _ = make_mock_env(seed=42)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}):
            with patch("agent.select_pilot", return_value=None) as choose:
                with patch("builtins.print"):
                    campaigns = Agent().act(env)

        choose.assert_called_once()
        self.assertEqual(len(env.pilot_history), 20)
        self.assertGreaterEqual(len(campaigns), 1)


if __name__ == "__main__":
    unittest.main()
