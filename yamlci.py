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
    def set_jobs(self, versions: list, requirements: str, scripts: dict):
        # TODO: Decompose this function into smaller, specialized functions

        # Add jobs to configuration
        self.yaml.update({'jobs': {}})

        # Add container job
        if scripts['docker']['img'] != '':
            self.yaml['jobs'].update({'container': {'runs-on': 'ubuntu-latest'}})

            # Add container to container job
            if len(scripts['docker']['img']) != 0: # Add container img
                self.yaml['jobs']['container'].update({'container': {'image': scripts['docker']['img']}})

            # Add steps to container job
            self.yaml['jobs']['container'].update({'steps': [{'uses': 'actions/checkout@v4'}]})

            # Add execs to container job
            if len(scripts['docker']['img']) != 0 and len(scripts['docker']['exec']) != 0: # Add container execs
                docker = '; '.join([' '.join(script[6:]) for script in scripts['docker']['exec']])
                self.yaml['jobs']['container']['steps'].append({
                    'name': 'Execute docker jobs',
                    'run': docker})
        
        # Add basic job
        if len(versions) != 0: 
            self.yaml['jobs'].update({'basic': {'runs-on': 'ubuntu-latest'}})
            self.yaml['jobs']['basic'].update({'strategy': {'matrix': {'python-version': versions}}}) # Add python-versions
            self.yaml['jobs']['basic'].update({'steps': [{'uses': 'actions/checkout@v4'}]}) # Add steps to basic job

            # Add pytest to job
            if len(scripts['pytest'][0]) != 0:
                pytest = '; '.join([' '.join(script) for script in scripts['pytest']])
                self.yaml['jobs']['basic']['steps'].extend( # Add setup-python and install dependencies
                    [{'name': 'Setup Python ${{ matrix.python-version }}',
                    'uses': 'actions/setup-python@v4',
                    'with': {'python-version': '${{ matrix.python-version }}'}},
                    {'name': 'Install Dependencies',
                    'run': f'python -m pip install --upgrade pip; pip install -r {requirements}'}])
                self.yaml['jobs']['basic']['steps'].append({'name': 'Run Pytest', 'run': f'pip install pytest; {pytest}'}) # Add pytest


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