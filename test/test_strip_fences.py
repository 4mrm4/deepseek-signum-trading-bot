"""Quick test of _strip_code_fences function."""
from deepseek_trading_bot import _strip_code_fences

tests = [
    ("plain",           '{"orders": []}',                         '{"orders": []}'),
    ("json_fence",      '```json\n{"orders": []}\n```',          '{"orders": []}'),
    ("no_lang_fence",   '```\n{"orders": []}\n```',              '{"orders": []}'),
    ("whitespace",      '  ```json\n{"orders": []}\n```  ',      '{"orders": []}'),
    ("raw_deepseek",    '```json\n{"orders": []}\n```',          '{"orders": []}'),
]

for name, inp, exp in tests:
    got = _strip_code_fences(inp)
    assert got == exp, f"{name}: expected {exp!r}, got {got!r}"
    print(f"  {name}: OK")

print("All _strip_code_fences tests PASSED")
