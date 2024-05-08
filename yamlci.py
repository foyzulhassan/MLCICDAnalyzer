from ruamel.yaml import YAML

# Class that builds .yaml files for CI/CD environments
class YamlCI:
    def __init__(self):
        self.yaml = {}

    # Set the workflow name of the yaml file
    def set_workflow_name(self, name: str):
        self.yaml.update({'name': name})

    # Set the branches of a basic workflow trigger of in the yaml file
    def set_workflow_trigger_branches(self, branches: list[str]):
        self.yaml.update({'on': {'push': {'branches': branches}}})

    # Set the jobs in the yaml file, including runtime versions, requirements, and a pytest invocation
    def set_jobs(self, versions: list, requirements: str, pytest: list[str]):
        self.yaml.update({'jobs': {'build': {'runs-on': 'ubuntu-latest', 'strategy': {'matrix': {'python-version': versions}}, 'steps': [ 
            {'uses': 'actions/checkout@v4'}, 
            {'name': 'Setup Python ${{ matrix.python-version }}',
             'uses': 'actions/setup-python@v4',
             'with': {'python-version': '${{ matrix.python-version }}'}},
            {'name': 'Install Dependencies',
             'run': f'python -m pip install --upgrade pip; pip install -r {requirements}'},
            {'name': 'Run Pytest',
             'run': f'pip install pytest; %s' % ' '.join(pytest)}
        ]}}})

    # Dump the yaml file, as it has been built, to a file
    def dump(self, path: str):
        with open(path, 'w') as file:
            yaml = YAML(typ='full', pure=True)
            yaml.default_flow_style = False
            yaml.indent(sequence=4, offset=2)
            yaml.sort_base_mapping_type_on_output = False
            yaml.default_style = None
            yaml.width = 100
            yaml.dump(data=self.yaml,
                      stream=file)