"""
Config loader. Returns the parsed config.yaml as a nested dict.
Access with cfg["section"]["key"].
"""
import yaml


def load_config(path: str) -> dict:
    """Load and return config.yaml as a nested dict.

    Args:
        path: Path to the YAML config file.

    Returns:
        Parsed config as a nested dict.
    """
    with open(path, "r") as f:
        return yaml.safe_load(f)
