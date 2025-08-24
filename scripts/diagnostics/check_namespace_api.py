#!/usr/bin/env python3
"""Check the Upstash Vector namespace API."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import inspect

from upstash_vector import Index

# Initialize with dummy values just to inspect the API
try:
    index = Index(url="https://dummy.upstash.io", token="dummy")

    print("Index methods:")
    for method in dir(index):
        if not method.startswith("_"):
            print(f"  - {method}")

    print("\nChecking upsert signature:")
    sig = inspect.signature(index.upsert)
    print(f"  upsert{sig}")

    print("\nChecking query signature:")
    sig = inspect.signature(index.query)
    print(f"  query{sig}")

    # Check if namespace is a method
    if hasattr(index, "namespace"):
        print("\nNamespace method found!")
        print(f"  Type: {type(index.namespace)}")

except Exception as e:
    print(f"Error: {e}")
