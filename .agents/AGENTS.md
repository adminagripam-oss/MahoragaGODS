### GitHub Actions & Node.js Warnings
- When encountering a warning about "Node.js 20 is deprecated" in GitHub Actions, recognize that it is a non-fatal warning and GitHub will automatically force it to run on Node 24.
- Do not treat the Node.js 20 deprecation warning as the root cause of a workflow failure (Exit Code 1). Always investigate the actual shell commands (e.g., Python scripts or tests) for the true failure cause.
- To minimize warnings, ensure we use the latest versions of actions (e.g., `actions/checkout@v4`, `actions/setup-python@v5`), but understand that until the action authors update their node environments, the warning may persist safely.
