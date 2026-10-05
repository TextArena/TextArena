"""Evaluate a model against a fixed opponent on a few games.

Needs `pip install "textarena[agents]" tinker` and the OPENROUTER_API_KEY and TINKER_API_KEY environment variables.
"""
import textarena as ta

agents = {
    "my-model": ta.agents.TinkerAgent(model_path="tinker://YOUR-RUN-ID/weights/YOUR-CHECKPOINT", max_tokens=512),
    "opponent": ta.agents.OpenRouterAgent(model_name="qwen/qwen3.8-27b"),
}

evaluation = ta.evaluate(agents, ["TicTacToe-v1", "Snake-v1"], episodes=8, workers=8)
for row in evaluation.summary():
    print(row)
