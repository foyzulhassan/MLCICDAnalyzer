import glob
import json
import logging
import os
from pathlib import Path
import time
import uuid

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, ScoredPoint, VectorParams
import subprocess

import recommend.utils as utils


class VectorRecommendations:
    def __init__(
        self, 
        project_name: str,
        workflow_path: str,
        requirements_path: str,
        target_paths: list[str],
        assemble_prompt_path: str,
        job_prompt_path: str,
        output_dir: str,
        duration_log_path: str,
        usage_log_path: str,
        chat_model: str,
        chat_api_key: str,
        embedding_hostname: str,
        embedding_port: str,
        embedding_model: str,
        embedding_api_key: str,
        hybrid_mode: bool = False,
        collection_name: str = 'sawra',
        max_chunks: int = 50,
        max_attempts: int = 5,
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
        self.project_name = project_name
        self.target_paths = target_paths
        self.hybrid_mode = hybrid_mode
        self.output_dir = output_dir
        self.scripts = self.__scripts()

        # Load the requirements file
        self.requirements_path = requirements_path
        with open(self.requirements_path, 'r') as file:
            self.requirements = file.read().strip().split('\n')

        # Initialize a chat model client and its metadata
        self.chat_model = chat_model
        self.client = OpenAI(api_key=chat_api_key)
        self.max_attempts = max_attempts
        
        # Initialize an embedding model client and its metadata
        self.embedding_model = embedding_model
        self.qdrant = QdrantClient(host=embedding_hostname, port=embedding_port, api_key=embedding_api_key, https=False)
        self.collection_name = collection_name
        self.version = 'hybrid'
        self.chunk_field = 'chunk'
        self.max_chunks = max_chunks

        # Load job prompt
        self.job_prompt_path = job_prompt_path
        with open(self.job_prompt_path, 'r') as file:
            self.job_prompt = file.read().strip()

        # Load assemble prompt
        self.assemble_prompt_path = assemble_prompt_path
        with open(self.assemble_prompt_path, 'r') as file:
            self.assemble_prompt = file.read().strip()

        # Initialize miscellaneous paths
        self.output_dir = output_dir

    def __duration(func):
        def wrapper(self, *args, **kwargs):
            # Calculate the duration
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Log the duration
            source = 'vector'
            function = str(func.__name__)
            self.duration_logger.info(f'"{source}","{function}","{duration}"')
            return result
        return wrapper

    @__duration
    def apply(self) -> dict:
        """Apply model recommendations to a workflow"""

        # Get the blocks for each job (i.e. target script)
        job_blocks = []
        for script in self.scripts:
            target_name = Path(script['filename']).stem
            
            # Get the inputs and dump it
            job_input = self.__inputs(script=script, target_name=target_name)
            job_input_path = os.path.join(self.output_dir, f'{target_name}.job.hybrid.yaml' if self.hybrid_mode else f'{target_name}.inputs.vector.txt')
            with open(job_input_path, 'w') as file:
                json.dump(job_input, file, indent=2)

            # Generate job blocks, or workflows for each job.
            job_block = self.__prompt(prompt=self.job_prompt, input=job_input)
            job_path = os.path.join(self.output_dir, f'{target_name}.job.hybrid.yaml' if self.hybrid_mode else f'{target_name}.job.vector.yaml')
            with open(job_path, 'w') as file:
                file.write(job_block)
            job_blocks.append(job_block)

        # Build the input for job block assembly
        assemble_input = \
        {
            'requirements': self.requirements,
            'shell_scripts': self.scripts,
            'jobs': job_blocks,
            'actionlint_errors': [],
        }
        if self.hybrid_mode:
            assemble_input['heuristic_yaml'] = self.workflow,

        # Attempt to assemble the workflow blocks multiple times
        assembled_workflow = ''
        for _ in range(self.max_attempts):
            # Sanitize and dump the assembled workflow
            assembled_workflow = self.__prompt(prompt=self.assemble_prompt, input=assemble_input)
            assembled_workflow = utils.sanitize_workflow(assembled_workflow)
            assembled_path = os.path.join(self.output_dir, f'{self.workflow_name}.hybrid.yaml' if self.hybrid_mode else f'{self.workflow_name}.vector.yaml')
            with open(assembled_path, 'w') as file:
                file.write(assembled_workflow)

            # Add the lint errors to the input for the next iteration (if any)
            actionlint_error = self.__actionlint(assembled_path)
            if actionlint_error is not None:
                assemble_input['actionlint_errors'].append(actionlint_error)
            else:
                break
        return assembled_workflow

    @__duration
    def __inputs(self, script: dict[str, str], target_name: str) -> dict[str, str]:
        """Get the input data that will be passed to the model"""

        # Get the embedding for the target script
        content = '\n'.join(script['content'])
        embedding = self.__embedding(content)

        # Get the runtime chunks for a runtime script
        runtime_chunks = {}
        for trace_type in ['strace', 'ltrace', 'pyenv']:
            points = self.__top_chunks(project_name=self.project_name, target_name=target_name, trace_type=trace_type, embedding=embedding)
            runtime_chunks[f"{target_name}.{trace_type}"] = [point.payload[self.chunk_field] for point in points]

        # Build the input and return it
        return \
        {
            'shell_script': script, 
            'requirements': self.requirements, 
            'runtime_chunks': runtime_chunks,
        }
    
    @__duration
    def __top_chunks(self, project_name: str, target_name: str, trace_type: str, embedding: list[float]) -> list[ScoredPoint]:
        """Fetch the top chunks within a qdrant"""
        return self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            query_filter=Filter(must=[
                FieldCondition(key='project', match=MatchValue(value=project_name)),
                FieldCondition(key='shell_file', match=MatchValue(value=target_name)),
                FieldCondition(key='file', match=MatchValue(value=f'{target_name}.{trace_type}'))
            ]),
            limit=self.max_chunks,
            with_payload=True)

    @__duration
    def __prompt(self, prompt: str, input: dict) -> str:
        """Prompt the LLM and pass it input data"""
        response = self.client.chat.completions.create(
            model=self.chat_model,
            temperature=0,
            messages=[
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': json.dumps(input, indent=2)},
            ])
        
        source = 'vector'
        purpose = 'generate'
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        self.usage_logger.info(f'"{source}","{purpose}","{prompt_tokens}","{completion_tokens}","{total_tokens}"')

        return response.choices[0].message.content
    
    @__duration
    def __embedding(self, text: str | list[str]) -> list[float]:
        """Get the vector embedding of text"""
        input = [text] if isinstance(text, str) else text
        response = self.client.embeddings.create(input=input, model=self.embedding_model)

        source = 'vector'
        purpose = 'embed'
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = total_tokens - prompt_tokens
        self.usage_logger.info(f'"{source}","{purpose}","{prompt_tokens}","{completion_tokens}","{total_tokens}"')

        return response.data[0].embedding

    @__duration
    def __actionlint(self, workflow_path: str) -> str | None:
        """Determine whether a workflow is valid using actionlint"""
        result = subprocess.run(['actionlint', workflow_path], capture_output=True, text=True)
        return result.stderr if result.returncode != 0 else None

    @__duration
    def __scripts(self) -> list[dict[str, str]]:
        """Load target scripts and their metadata"""
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
        return scripts
    

class QdrantVectorizer:
    def __init__(
        self,
        project_name: str,
        output_dir: str,
        duration_log_path: str,
        usage_log_path: str,
        embedding_hostname: str,
        embedding_port: int,
        embedding_api_key: str,
        embedding_model: str,
        collection_name: str = 'sawra',
        chunk_size: int = 3000,
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

        # Initialize project metadata
        self.project_name = project_name
        self.output_dir = output_dir

        # Initialize embedding vector
        self.openai_client = OpenAI(api_key=embedding_api_key)
        self.qdrant_client = QdrantClient(host=embedding_hostname, port=embedding_port, api_key=embedding_api_key, https=False)
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.embedding_model = embedding_model
        self.embedding_api_key = embedding_api_key
    
    def __duration(func):
        def wrapper(self, *args, **kwargs):
            # Calculate the duration
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Log the duration
            source = 'qdrant'
            function = str(func.__name__)
            self.duration_logger.info(f'"{source}","{function}","{duration}"')
            return result
        return wrapper

    @__duration
    def vectorize(self) -> None:
        """Vectorize target traces and upload them"""
        self.__ensure_collections()

        # Load the trace summary file
        summary_path = os.path.join(self.output_dir, 'summary.json')
        with open(summary_path, 'r') as file:
            summary = json.load(file)

        # Iterate through traces, chunk them, and embed them
        for trace_path, traced_values in summary.items():
            parsed = traced_values if isinstance(traced_values, list) else [f'"{k}": "{v}"' for k, v, in traced_values.items()]
            parsed = '\n'.join(parsed)
            chunks = self.__chunk_text(parsed)

            # Iterate through chunks and embed them
            for i, chunk in enumerate(chunks):
                id = str(uuid.uuid4())
                embedding = self.__embedding(chunk)
                payload = \
                {
                    'project': self.project_name,
                    'file': Path(trace_path).name,
                    'shell_file': Path(trace_path).stem,
                    'chunk': chunk,
                    'chunk_id': i,
                }
                self.qdrant_client.upsert \
                (
                    collection_name=self.collection_name,
                    points=[qmodels.PointStruct(id=id, vector=embedding, payload=payload)],
                )
    
    @__duration
    def __ensure_collections(self) -> None:
        """Ensure that all collections exist (and create them if they don't)"""
        if not self.qdrant_client.collection_exists(self.collection_name):
            self.qdrant_client.recreate_collection \
            (
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

    @__duration
    def __embedding(self, text: str | list[str]) -> list[float]:
        """Get text embeddings from an embedding model"""
        input = [text] if isinstance(text, str) else text
        response = self.openai_client.embeddings.create(input=input, model=self.embedding_model)

        source = 'qdrant'
        purpose = 'embed'
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = total_tokens - prompt_tokens
        self.usage_logger.info(f'"{source}","{purpose}","{prompt_tokens}","{completion_tokens}","{total_tokens}"')

        return response.data[0].embedding

    @__duration
    def __chunk_text(self, text: str) -> list[str]:
        """Chunk the provided text based on the maximum chunk size"""
        return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]
