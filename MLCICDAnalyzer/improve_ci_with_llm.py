import os
from openai import OpenAI

class ImproveCIWithLLM:
    def __init__(self, api_key=None):
        # Initialize the OpenAI client with the API key
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def improve_ci(self, requirements, generated_yaml, project_description, ci_instructions, prompt_file):
       
        with open(requirements, 'r') as file:
            requirements_content = file.read()

        with open(generated_yaml, 'r') as file:
            generated_yaml_content = file.read()

        with open(project_description, 'r') as file:
            project_description_content = file.read()

        with open(ci_instructions, 'r') as file:
            ci_instructions_content = file.read()

        # Read the prompt template
        with open(prompt_file, 'r') as file:
            prompt_template = file.read()

        # Prepare placeholders
        placeholders = {
            '{project_description}': project_description_content,
            '{ci_instructions}': ci_instructions_content,
            '{requirements}': requirements_content,
            '{generated_yaml}': generated_yaml_content
        }

        # Replace placeholders in the prompt
        for placeholder, content in placeholders.items():
            prompt_template = prompt_template.replace(placeholder, content)

        # Construct the message payload
        messages = [
    {
        "role": "system",
        "content": (
            "You are an expert CI/CD developer specializing in GitHub Actions workflows. "
            "Your expertise includes creating, optimizing, and maintaining CI/CD scripts for software projects of varying complexity. "
            "You understand best practices, industry standards, and effective methods for making CI workflows secure, efficient, and maintainable. "
            "Your task is to ensure the CI script meets industry standards and is optimized for readability, performance, and security."
        )
    },
    {
        "role": "user",
        "content": (
            f"{prompt_template}\n\n"
            "### Important Considerations:\n"
            "- Ensure all dependencies present in the YAML file but missing in `requirements.txt` are retained in the YAML file.\n"
            "- Validate and enhance the YAML file for GitHub Actions compatibility, adhering to YAML syntax rules and best practices.\n"
            "- Output **only** the final improved YAML file without any explanations or comments."
            )
        }
    ]

        # Call the OpenAI API
        chat_completion = self.client.chat.completions.create(
            messages=messages,
            model="gpt-4",
            temperature=0
        )

        # Extract and return the improved YAML
        ciyaml_improved_by_llm = chat_completion.choices[0].message.content
        return ciyaml_improved_by_llm
