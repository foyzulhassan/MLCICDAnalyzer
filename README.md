# CI Configuration Generator
Automatically generate robust Continuous Integration (CI) configurations for GitHub Actions from existing application deployments.

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
    - [Target Wrapper](#target-wrapper)
    - [How to Run](#how-to-run)
- [License](#license)

## Installation
```console
cd MLCICDAnalyzer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
### Target Wrapper
Pathing issues can occur when selecting target scripts in directories other than this project's root. Because of this, **all targets must be enclosed within the wrapper provided below.** The `--target` argument should point to this wrapper (or a directory of these wrappers):

```console
# !/bin/bash
home=$PWD # Save the current directory
cd $(dirname "$0") # Navigate to the target's directory (this script must be in the same directory as the target)

INSERT_COMMAND(S)_TO_RUN_THE_TARGET_HERE # Run the target

cd $home
```

### How to Run
1. Create the appropriate wrapper for the target scripts
2. Run the following command with your arguments to generate **one new basic configuration:**
    ```console
    python3 src/genci --target \<PATH\> --requirement \<PATH\> --workflow \<PATH\> --workflow_name \<NAME\> --new_trace
    ```

## License
TBD

python3 -m genci   --requirements /home/rchavan/ci_tool/test-projects/yolov5/requirements.txt   --workflow /home/rchavan/ci_tool/test-projects/yolov5-scripts/generations/workflow.yaml   --project_description /home/rchavan/ci_tool/test-projects/yolov5-scripts/project_description.txt   --ci_instructions /home/rchavan/ci_tool/test-projects/yolov5-scripts/instructions.txt   --prompt_file /home/rchavan/ci_tool/test-projects/yolov5-scripts/prompt.txt   --workflow_name workflow   --api_key <api-key>  --target /home/rchavan/ci_tool/test-projects/yolov5-scripts/targets