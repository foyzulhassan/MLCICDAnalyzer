from tracing import Tracing
import ruamel.yaml
from ruamel.yaml import YAML
from pathlib import Path

# Class that builds .yaml files for CI/CD environments
class YamlCI:
    def __init__(self, tracing: Tracing, name='Workflow', triggers={'push': {'branches': ['main']}}):
        self.yaml = {'name': name, 'on': triggers, 'jobs': {}}
        self.tracing = tracing
        self.set_job_containers()
        self.set_basic_jobs()
        self.set_service_containers()

    # Add jobs that use job containers to yaml
    def set_job_containers(self):
        # Stop if the job container does not have an image
        if self.tracing.job_containers['docker']['img'] == []:
            return

        # Add image to job container
        self.yaml['jobs'].update({'job': {'runs-on': 'ubuntu-latest'}}) # Add runner to job container
        self.yaml['jobs']['job'].update({'container': {'image': self.tracing.job_containers['docker']['img']}}) # Add container and image to job container
        if self.tracing.versions != []:
            self.yaml['jobs']['job'].update({'strategy': {}}) # Add strategy to job container
        self.yaml['jobs']['job'].update({'steps': [{'uses': 'actions/checkout@v4'}]}) # Add repository checkout action to job container

        # Stop if job container does not have execution scripts
        if len(self.tracing.job_containers['docker']['exec']) == 0:
            return
        
        # Add execs to job container
        docker = '; '.join([' '.join(script[6:]) for script in self.tracing.job_containers['docker']['exec']]) # Remove docker invocations from scripts
        self.yaml['jobs']['job']['steps'].append({ # Add scripts to the job container execs
            'name': 'Execute Docker Scripts',
            'run': docker})

    # Add jobs that use service containers to yaml
    def set_service_containers(self):
        # Stop if there are no service containers
        if len(self.tracing.service_containers) == 0:
            return
        
        # Add a job if it does not already exist
        if len(self.yaml['jobs']) == 0:
            self.yaml['jobs'].update({'job': {'runs-on': 'ubuntu-latest'}})
        
        # Add services to job
        if len(self.tracing.service_containers) > 0:
            self.yaml['jobs']['job'].update({'services': {}})
            for container in self.tracing.service_containers:
                image_name = container[0].split(':')[0]
                if image_name not in self.yaml['jobs']['job']['services']:   
                    self.yaml['jobs']['job']['services'].update({image_name: {'image': container[0], 'ports': container[1]}})
                else:
                    self.yaml['jobs']['job']['services'][image_name]['ports'].extend(container[1])

    # Add basic jobs that may use service containers to yaml
    def set_basic_jobs(self):  
        # Stop if there is no runtime version information
        # if len(self.tracing.versions) == 0:
        #     return
        
        # Add a job if it does not already exist
        if len(self.yaml['jobs']) == 0:
            self.yaml['jobs'].update({'job': {'runs-on': 'ubuntu-latest'}})

        # Add basic runtime configurations
        if self.tracing.versions != []:
            self.yaml['jobs']['job'].update({'strategy': {'matrix': {'python-version': self.tracing.versions}}}) # Add python-versions
        if 'steps' not in self.yaml['jobs']['job']:
            self.yaml['jobs']['job'].update({'steps': [{'uses': 'actions/checkout@v4'}]}) # Add steps to basic job
        
        # Add runtime setup and install dependencies
        if self.tracing.versions != []:
            self.yaml['jobs']['job']['steps'].extend( 
                [{'name': 'Setup Python ${{ matrix.python-version }}',
                'uses': 'actions/setup-python@v4',
                'with': {'python-version': '${{ matrix.python-version }}'}},
                {'name': 'Install Dependencies',
                'run': f'python -m pip install --upgrade pip; pip install -r requirements.txt'}])

        # Add additional runtime scripts
        compiled_script = '; '.join([' '.join(script) for script in self.tracing.scripts if 'docker' not in script[0]])
        if len(compiled_script) > 0:
            self.yaml['jobs']['job']['steps'].append({'name': 'Execute Basic Scripts', 'run': compiled_script})

    # Dump the yaml file, as it has been built, to a file
    def dump(self, path: str):
        with open(path, 'w') as file:
            yaml = YAML(typ='full', pure=True)
            yaml.default_flow_style = False
            yaml.indent(sequence=4, offset=2)
            yaml.sort_base_mapping_type_on_output = False
            yaml.default_style = None
            yaml.width = 100
            yaml.ignore_aliases = lambda *args : True
            yaml.dump(data=self.yaml,
                      stream=file)
            
        # Remove aliases from yaml
        # TODO: Find cleaner way to remove aliases
        file = Path(path)  
        ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
        yaml = YAML(pure=True)
        data = yaml.load(file)
        yaml.dump(data, file)