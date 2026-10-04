from textarena.envs.registration import register_with_versions

register_with_versions(
    id="WinAsMuchAsYouCan-v1",
    entry_point="textarena.envs.WinAsMuchAsYouCan.env:WinAsMuchAsYouCanEnv",
)
