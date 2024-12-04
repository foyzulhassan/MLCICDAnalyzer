import yaml

class YamlParser:
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file
        self.workflow = None

    def preprocess_yaml(self):
        """
        Preprocess the YAML file to remove surrounding ```yaml and ```
        """
        try:
            with open(self.yaml_file, 'r') as file:
                lines = file.readlines()

            if lines[0].strip() == "```yaml":
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned_content = "".join(lines)
            with open(self.yaml_file, 'w') as file:
                file.write(cleaned_content)
        except Exception as e:
            raise ValueError(f"Error during YAML preprocessing: {e}")

    def validate_yaml(self):
        """
        Validate if the provided YAML file is well-formed.
        """
        try:
            self.preprocess_yaml()
            with open(self.yaml_file, 'r') as file:
                self.workflow = yaml.safe_load(file)
            print(f"YAML file '{self.yaml_file}' is valid.")
            return True
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML file '{self.yaml_file}': {exc}")
        except FileNotFoundError:
            raise FileNotFoundError(f"YAML file '{self.yaml_file}' not found.")

    def get_workflow(self):
        """
        Returns the parsed workflow if valid.
        """
        if not self.workflow:
            raise ValueError("Workflow not loaded. Please validate YAML first.")
        return self.workflow
