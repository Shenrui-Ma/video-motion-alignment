import sys
from pathlib import Path

def official_basic_guider_class(actual, expected):
    """Accept the official class loaded under Comfy's absolute-path module alias.

    Comfy's node loader uses the file path without .py as the module name,
    whereas importing comfy_extras.nodes_custom_sampler creates another class.
    Permit only the same source file, direct base and exact class method code.
    A similarly named class, subclass or modified class remains unsupported.
    """
    if actual is expected:
        return True
    if actual.__name__ != "Guider_Basic" or expected.__name__ != "Guider_Basic":
        return False
    actual_module = sys.modules.get(actual.__module__)
    expected_module = sys.modules.get(expected.__module__)
    if actual_module is None or expected_module is None:
        return False
    actual_file = getattr(actual_module, "__file__", None)
    expected_file = getattr(expected_module, "__file__", None)
    if not actual_file or not expected_file:
        return False
    if Path(expected_file).name != "nodes_custom_sampler.py" or Path(actual_file).resolve() != Path(expected_file).resolve():
        return False
    if getattr(actual_module, "Guider_Basic", None) is not actual or actual.__bases__ != expected.__bases__:
        return False
    if set(vars(actual)) != set(vars(expected)) or actual.__qualname__ != expected.__qualname__:
        return False
    method = vars(actual).get("set_conds")
    expected_method = vars(expected).get("set_conds")
    if getattr(method, "__code__", None) is None or method.__code__ != getattr(expected_method, "__code__", None):
        return False
    # The official class only overrides set_conds. Refuse any future additional
    # class implementation until the frozen sampling contract is re-audited.
    return set(vars(actual)) == {"__module__", "set_conds", "__doc__"}

