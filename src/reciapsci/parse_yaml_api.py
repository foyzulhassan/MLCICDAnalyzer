import yaml

def validate_yaml(yaml_file):
    """
    Validate if the provided YAML file is well-formed.
    """
    try:
        with open(yaml_file, 'r') as file:
            yaml.safe_load(file)
        return True
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}")
        return False
