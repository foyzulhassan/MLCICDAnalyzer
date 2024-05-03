import yaml

# Class that builds .yaml files for CI/CD environments
class YamlCI:
    def __init__(self):
        self.yaml = {}
    
    # Set the workflow name of the yaml file
    def set_workflow_name(self, name: str):
        self.yaml.update({'name': name})

    # Set the branches of a basic workflow trigger of in the yaml file
    def set_workflow_trigger_branches(self, branches: list[str]):
        # PyYAML will dump 'on' as a string because on is recognized as a boolean value in YAML 1.1
        self.yaml.update({'on': {'push': {'branches': branches}}})

    # Set the jobs in the yaml file, including runtime versions, requirements, and a pytest invocation
    def set_jobs(self, versions: list, requirements: str, pytest: list[str]):
        self.yaml.update({'jobs': {'build': {'runs-on': 'ubuntu-latest', 'strategy': {'matrix': {'python-version': versions}}, 'steps': [ 
            {'uses': 'actions/checkout@v4'}, 
            {'name': 'Setup Python',
             'uses': 'actions/setup-python@v4',
             'with': {'python-version': '${{ matrix.python-version }}'}},
            {'name': 'Install Dependencies',
             'run': f'| python -m pip install --upgrade pip\npip install pytest\npip install -r {requirements}'},
            {'name': 'Run Pytest',
             'run': ' '.join(pytest)}
        ]}}})
    
    # Dump the yaml file, as it has been built, to a file
    def dump(self, path: str):
        with open(path, 'w') as file:
            yaml.safe_dump(data=self.yaml,
                                  stream=file,
                                  allow_unicode=True,
                                  sort_keys=False)