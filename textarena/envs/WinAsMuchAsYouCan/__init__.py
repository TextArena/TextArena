from textarena.envs.registration import register

register(
    id="WinAsMuchAsYouCan-v1",
    entry_point="textarena.envs.WinAsMuchAsYouCan.env:WinAsMuchAsYouCanEnv",
)
