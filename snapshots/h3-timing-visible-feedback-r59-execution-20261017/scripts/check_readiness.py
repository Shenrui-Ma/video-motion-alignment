"""Inspect remaining migration gates; exits2 while production is unavailable."""
import json
from execution_contract import readiness

if __name__ == '__main__':
    result = readiness()
    print(json.dumps(result, indent=2))
    raise SystemExit(2 if result['status'] == 'BLOCKED' else 0)
