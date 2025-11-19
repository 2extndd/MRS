#!/usr/bin/env python3
"""
Test script for proxy parser
Tests the new parse_proxy_string function with various formats
"""

import sys
sys.path.insert(0, '.')

from proxies import parse_proxy_string

# Test cases
test_cases = [
    # Format: ip:port:user:pass
    ("82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h", "http://wtllhdak:9vxcxlvhxv1h@82.21.62.51:7815"),
    
    # Format: ip:port (no auth)
    ("192.168.1.1:8080", "http://192.168.1.1:8080"),
    
    # Format: already correct (http://)
    ("http://user:pass@10.0.0.1:3128", "http://user:pass@10.0.0.1:3128"),
    
    # Invalid formats
    ("invalid", None),
    ("", None),
    (None, None),
]

print("Testing proxy parser...")
print("=" * 80)

passed = 0
failed = 0

for test_input, expected in test_cases:
    result = parse_proxy_string(test_input)
    
    if result == expected:
        status = "✅ PASS"
        passed += 1
    else:
        status = "❌ FAIL"
        failed += 1
    
    print(f"{status}")
    print(f"  Input:    {test_input}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
    print()

print("=" * 80)
print(f"Results: {passed} passed, {failed} failed")

if failed == 0:
    print("✅ All tests passed!")
    sys.exit(0)
else:
    print("❌ Some tests failed!")
    sys.exit(1)
