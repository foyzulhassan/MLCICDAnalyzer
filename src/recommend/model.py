import json
import logging
import os
from pathlib import Path
import time

from openai import OpenAI
from openai.types import CreateEmbeddingResponse
from openai.types.chat import ChatCompletion

import recommend.utils as utils


class ModelRecommendations:
    def __init__(
        self,
        workflow_path: str,
        target_paths: list[str],
        requirements_path: str,
        template_path: str,
        instruction_path: str,
        output_dir: str,
        api_key: str, 
        chat_model: str,
    ) -> None:
        # Load and initialize a workflow and its metadata
        self.workflow_path = workflow_path
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_str = utils.workflow_to_str(self.workflow)
        self.target_paths = target_paths
        self.output_dir = output_dir

        # Load the requirements file
        self.requirements_path = requirements_path
        with open(self.requirements_path, 'r') as file:
            self.requirements = file.read().strip().split('\n')

        # Initialize a model client and its metadata
        self.api_key = api_key
        self.chat_model = chat_model
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

    def __log_duration(func):
        """Decorator that logs the duration of the decorated function"""
        def wrapper(self, *args, **kwargs):
            # Calculate the duration of the caller
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Get the qualified name of the caller
            filename = os.path.basename(__file__)
            classname = 'ModelRecommendations'
            qualname = f'{filename}.{classname}.{func.__name__}'

            # Log the qualname and duration of the decorated function
            message = f'"{qualname}","{start_time}","{end_time}","{duration}"'
            logging.getLogger('duration').info(message)
            return result
        return wrapper

    @__log_duration
    def apply(self) -> dict:
        """Apply model recommendations to a workflow"""

        # Prompt the model using the instructions and inputs
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {'role': 'system', 'content': self.instructions},
                {'role': 'user', 'content': self.inputs},
            ],
            temperature=0,
            max_tokens=16383,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0)
        self.__log_costs('apply', response)
        
        # Localize the workflow string and parse it into a dict
        workflow = response.choices[0].message.content
        workflow = utils.sanitize_workflow(workflow)
        
        # Dump and return the workflow
        with open(self.model_workflow_path, 'w') as file:
            file.write(workflow)
        return workflow
    
    @__log_duration
    def __inputs(self) -> dict[str, str]:
        """Get the filled input template that will be passed to the model"""

        # Load target scripts and their metadata
        scripts = []
        for path in self.target_paths:
            with open(path, 'r') as file:
                content = file.read()
            script = \
            {
                'script_name': Path(path).stem, 
                'script_content': content.strip().split('\n'),
                'script_python_requirements': self.requirements,
            }
            scripts.append(script)
        inputs = {'bash_scripts': scripts}

        # Dump the filled input template to a file and return it
        out_path = os.path.join(self.output_dir, 'inputs.model.json')
        with open(out_path, 'w') as file:
            json.dump(inputs, file, indent=2)
        return inputs
    
    def __log_costs(self, funcname: str, response: ChatCompletion | CreateEmbeddingResponse) -> None:
        """Log the embedding/prompting costs that have been accumulated"""

        # Get the qualified name of the caller
        filename = os.path.basename(__file__)
        classname = 'ModelRecommendations'
        qualname = f'{filename}.{classname}.{funcname}'

        # Get the token usage statistics
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = total_tokens - prompt_tokens

        # Log the cost of the caller
        message = f'"{qualname}","{prompt_tokens}","{completion_tokens}","{total_tokens}"'
        logging.getLogger('cost').info(message)
