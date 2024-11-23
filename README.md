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
1. Launch a Linux-based environment
2. Install Python3 (with tkinter) within the environment 
3. Install target dependencies within the environment
4. **Create the appropriate wrapper for the target within the environment**
5. Clone this project and navigate to its root directory
6. Run the following command with your arguments to generate **one new basic configuration:**
    ```console
    python3 main.py --target \<PATH\> --requirement \<PATH\> --workflow \<PATH\> --workflow_name \<NAME\> --new_trace
    ```

## License
TBD