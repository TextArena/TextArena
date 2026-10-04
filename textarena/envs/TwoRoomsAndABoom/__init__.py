from textarena.envs.registration import register_with_versions

register_with_versions(
    id="TwoRoomsAndABoom-v1",
    entry_point="textarena.envs.TwoRoomsAndABoom.env:TwoRoomsAndABoomEnv",
    num_rounds=3, cards_per_room=3, discussion_rounds=2,
)
