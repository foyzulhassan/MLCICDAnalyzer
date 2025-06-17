import json
import logging
import os
from pathlib import Path
import time

from openai import OpenAI

import recommend.utils as utils


class ModelRecommendations:
    def __init__(
        self,
        workflow_path: str,
        target_paths: list[str],
        template_path: str,
        instruction_path: str,
        output_dir: str,
        duration_log_path: str,
        usage_log_path: str,
        api_key: str, 
        model: str = 'gpt-4o-mini',
    ) -> None:
        # Initialize a duration logger
        self.duration_log_path = duration_log_path
        self.duration_logger = logging.getLogger(f'{__name__}.duration')
        self.duration_logger.setLevel(logging.INFO)
        self.duration_handler = logging.FileHandler(self.duration_log_path)
        self.duration_handler.setFormatter(logging.Formatter('%(message)s'))
        self.duration_logger.addHandler(self.duration_handler)

        # Initialize a usage logger
        self.usage_log_path = usage_log_path
        self.usage_logger = logging.getLogger(f'{__name__}.usage')
        self.usage_logger.setLevel(logging.INFO)
        self.usage_handler = logging.FileHandler(self.usage_log_path)
        self.usage_handler.setFormatter(logging.Formatter('%(message)s'))
        self.usage_logger.addHandler(self.usage_handler)

        # Load and initialize a workflow and its metadata
        self.workflow_path = workflow_path
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_str = utils.workflow_to_str(self.workflow)
        self.target_paths = target_paths
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

    def __duration(func):
        def wrapper(self, *args, **kwargs):
            # Calculate the duration
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Log the duration
            source = 'model'
            function = str(func.__name__)
            self.duration_logger.info(f'"{source}","{function}","{duration}"')
            return result
        return wrapper

    @__duration
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
        
        # Log the usage
        source = 'model'
        purpose = 'generate'
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        self.usage_logger.info(f'"{source}","{purpose}","{prompt_tokens}","{completion_tokens}","{total_tokens}"')
        
        # Localize the workflow string and parse it into a dict
        workflow = response.choices[0].message.content
        workflow = utils.sanitize_workflow(workflow)
        
        # Dump and return the workflow
        utils.dump_workflow(workflow, self.model_workflow_path)
        return workflow
    
    @__duration
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
        out_path = os.path.join(self.output_dir, 'inputs.model.txt')
        with open(out_path, 'w') as file:
            file.write(template)
        return template
