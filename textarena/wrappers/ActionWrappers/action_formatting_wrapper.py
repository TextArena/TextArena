from textarena.core import ActionWrapper, Env

__all__ = ["ActionFormattingWrapper"]


class ActionFormattingWrapper(ActionWrapper):
    """
    A wrapper that formats actions by adding brackets if they're missing.
    
    This wrapper ensures that all actions follow a consistent format by wrapping
    them in square brackets if they don't already contain brackets. This is useful
    for environments that require actions to be enclosed in brackets but where
    agents might not always follow this convention.
    
    Example:
        - Input: "move north"
        - Output: "[move north]"
        
        - Input: "[trade wheat]"
        - Output: "[trade wheat]" (unchanged)
    """

    def __init__(self, env: Env):
        """
        Initialize the ActionFormattingWrapper.
        
        Args:
            env (Env): The environment to wrap.
        """
        super().__init__(env)

    def action(self, action: str) -> str:
        """
        Format the action by adding brackets if they're missing.
        
        This method checks if the action already contains square brackets.
        If not, it wraps the entire action string in square brackets.
        
        Args:
            action (str): The action to format.
            
        Returns:
            str: The formatted action, with brackets added if necessary.
        """
        action = action.strip().strip("'\"")
        
        if "[" not in action and "]" not in action:
            return f"[{action}]"
        else:
            return action