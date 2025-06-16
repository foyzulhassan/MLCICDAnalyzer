import json
import os
from pathlib import Path

from openai import OpenAI

import recommend.utils as utils


class ModelRecommendations:
    def __init__(
        self,
        workflow_path: str,
        schema_path: str,
        target_paths: list[str],
        template_path: str,
        instruction_path: str,
        output_dir: str,
        api_key: str, 
        model: str = 'gpt-4o',
    ) -> None:
        # Load and initialize a workflow and its metadata
        self.workflow_path = workflow_path
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_str = utils.workflow_to_str(self.workflow)
        self.target_paths = target_paths
        
        # Load and initialize a workflow validation schema
        self.schema_path = schema_path
        with open(self.schema_path, 'r') as schema_file:
            self.schema = json.load(schema_file)
        self.output_dir = output_dir

        # Initialize a model client and its metadata
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        
        # Load the model input data
        self.template_path = template_path
        self.inputs = utils.workflow_to_str(self.__inputs()).strip()

        # Load the system instructions
        self.instruction_path = instruction_path
        with open(self.instruction_path, 'r') as file:
            self.instructions = file.read().strip()

        # Initialize miscellaneous paths
        self.output_dir = output_dir
        self.model_workflow_path = os.path.join(self.output_dir, f'{self.workflow_name}.model.yaml')

    def apply(self) -> dict:
        """Apply model recommendations to a workflow"""

        # Prompt the model using the instructions and inputs
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.instructions},
                {'role': 'user', 'content': self.inputs},
            ],
            temperature=0,
            max_tokens=16383,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0)
        
        # Localize the workflow string and parse it into a dict
        workflow = response.choices[0].message.content
        lines = workflow.splitlines()
        if lines and lines[0].strip().lower() == "```yaml":
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        workflow = '\n'.join(lines)
        workflow = utils.workflow_to_dict(workflow)
        
        # Dump and return the workflow
        utils.dump_workflow(workflow, self.model_workflow_path)
        return workflow
        
    def __inputs(self) -> dict[str, str]:
        """Get the filled input template that will be passed to the model"""

        # Load target scripts and their metadata
        scripts = []
        for path in self.target_paths:
            with open(path, 'r') as file:
                content = file.read()
            script = \
            {
                'filename': Path(path).name, 
                'content': content.strip().split('\n'),
            }
            scripts.append(script)

        # Fill in the input template with input data
        with open(self.template_path, 'r') as file:
            template = file.read()
        script_str = json.dumps({'shell_scripts': scripts}, indent=2)
        template = template.replace('<<input_object_1>>', script_str)

        # Dump the filled input template to a file and return it
        out_path = os.path.join(self.output_dir, 'inputs.llm.txt')
        with open(out_path, 'w') as file:
            file.write(template)
        return template


class HybridRecommendations:
    def __init__(self):
        pass
