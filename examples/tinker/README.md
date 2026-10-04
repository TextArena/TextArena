# Tinker self-play training

This example trains a policy on TextArena through asynchronous mirror
self-play.

- `train_selfplay.py` contains the configuration and learning loop.
- `rollouts.py` contains game workers, prompting, and trajectory collection.

The model may reason freely, but its final move must be wrapped in
`<action>...</action>`. For example:

```text
The center is strongest.
<action>4</action>
```

Only `4` is sent to `env.step`. Training uses each environment's `-mdp`
variant so every turn's observation contains the complete information needed
to act.

Install the optional dependency and provide an API key:

```bash
pip install "TextArena[all]"
export TINKER_API_KEY=...
python examples/tinker/train_selfplay.py
```

Edit `Config` at the bottom of `train_selfplay.py` to choose environments and
training settings.
