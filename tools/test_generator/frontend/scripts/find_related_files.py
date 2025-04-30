#!/usr/bin/env python3
"""
Script to find test files related to frontend source files (JS, TS, Svelte).
Usage: python find_related_test_files.py <file_list> <project_root>
"""

import os
import sys
import json
import re
from collections import defaultdict

def find_test_file(source_file, project_root):
    """Find test files that might be related to a given source file."""
    related_test_files = []
    
    # Get the path relative to project root
    if os.path.isabs(source_file):
        rel_path = os.path.relpath(source_file, project_root)
    else:
        rel_path = source_file
        source_file = os.path.join(project_root, rel_path)
    
    if not os.path.exists(source_file):
        return []
        
    # Get file details
    file_dir = os.path.dirname(rel_path)
    file_name = os.path.basename(rel_path)
    file_base, file_ext = os.path.splitext(file_name)
    
    # Common test file patterns
    test_patterns = [
        # Same directory, test suffix
        (file_dir, f"{file_base}.test{file_ext}"),
        (file_dir, f"{file_base}.spec{file_ext}"),
        
        # In __tests__ directory next to the file
        (os.path.join(file_dir, "__tests__"), f"{file_base}.test{file_ext}"),
        (os.path.join(file_dir, "__tests__"), f"{file_base}.spec{file_ext}"),
        
        # In tests directory next to the file
        (os.path.join(file_dir, "tests"), f"{file_base}.test{file_ext}"),
        (os.path.join(file_dir, "tests"), f"{file_base}.spec{file_ext}"),
        
        # In test directory next to the file
        (os.path.join(file_dir, "test"), f"{file_base}.test{file_ext}"),
        (os.path.join(file_dir, "test"), f"{file_base}.spec{file_ext}"),
        
        # In parallel test directory structure
        (file_dir.replace("src/", "tests/"), f"{file_base}.test{file_ext}"),
        (file_dir.replace("src/", "tests/"), f"{file_base}.spec{file_ext}"),
        
        # Project root tests directory
        (os.path.join("tests", file_dir), f"{file_base}.test{file_ext}"),
        (os.path.join("tests", file_dir), f"{file_base}.spec{file_ext}"),
        
        # For SvelteKit routes, check for similar paths in test directory
        (file_dir.replace("src/routes", "tests/routes"), f"{file_base}.test{file_ext}"),
        (file_dir.replace("src/routes", "tests/routes"), f"{file_base}.spec{file_ext}"),
        
        # Component tests in e2e tests
        (file_dir.replace("src/components", "tests/e2e/components"), f"{file_base}.test{file_ext}"),
        (file_dir.replace("src/components", "tests/e2e/components"), f"{file_base}.spec{file_ext}"),
        
        # For TypeScript files, also check JavaScript test files
        (file_dir, f"{file_base}.test.js"),
        (file_dir, f"{file_base}.spec.js"),
        
        # Special case for index files
        (os.path.join(file_dir, "__tests__"), "index.test.js"),
        (os.path.join(file_dir, "__tests__"), "index.spec.js"),
        (os.path.join(file_dir, "__tests__"), "index.test.ts"),
        (os.path.join(file_dir, "__tests__"), "index.spec.ts"),
        
        # Check for Playwright test files
        (os.path.join("tests", "e2e"), f"{file_base}.spec.ts"),
        (os.path.join("tests", "e2e"), f"{file_base}.test.ts"),
        
        # Check for Vitest files
        (os.path.join("tests", "unit"), f"{file_base}.spec.ts"),
        (os.path.join("tests", "unit"), f"{file_base}.test.ts"),
    ]
    
    # Check all test patterns
    for test_dir, test_file in test_patterns:
        test_path = os.path.join(project_root, test_dir, test_file)
        if os.path.exists(test_path):
            # Add relative path to project root
            rel_test_path = os.path.relpath(test_path, project_root)
            related_test_files.append(rel_test_path)
    
    # Try to find test files that reference this file
    component_name = file_base
    # Convert kebab-case or snake_case to PascalCase for component matching
    if "-" in component_name or "_" in component_name:
        words = re.split(r'[-_]', component_name)
        component_name = ''.join(word.capitalize() for word in words)
    
    # Look for test files that might reference this component by name
    for root, _, files in os.walk(os.path.join(project_root, "tests")):
        for file in files:
            if file.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts", ".test.svelte", ".spec.svelte")):
                test_path = os.path.join(root, file)
                
                # Check if the file contains references to our component
                try:
                    with open(test_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if (component_name in content or file_base in content or 
                            os.path.basename(file_dir) in content):
                            rel_test_path = os.path.relpath(test_path, project_root)
                            related_test_files.append(rel_test_path)
                except Exception as e:
                    print(f"Error reading test file {test_path}: {e}", file=sys.stderr)
    
    return list(set(related_test_files))  # Remove duplicates

def process_files_from_list(file_list_path, project_root):
    """Process a list of files and find related test files."""
    with open(file_list_path, 'r') as f:
        interesting_files = [line.strip() for line in f if line.strip()]
    
    # Dictionary to store each file and its related test files
    test_map = defaultdict(list)
    all_test_files = set()
    
    for file in interesting_files:
        # Normalize file path to be relative to project root
        if os.path.isabs(file):
            rel_file = os.path.relpath(file, project_root)
        else:
            rel_file = file
        
        # Skip test files themselves
        if ".test." in rel_file or ".spec." in rel_file or "/tests/" in rel_file or "/__tests__/" in rel_file:
            continue
            
        # Find related test files
        test_files = find_test_file(rel_file, project_root)
        if test_files:
            test_map[rel_file] = test_files
            all_test_files.update(test_files)
    
    # Write results to a JSON file to maintain structure
    with open('test_files_map.json', 'w') as f:
        json.dump(test_map, f, indent=2)
    
    # Write all test files to a text file
    with open('all_test_files.txt', 'w') as f:
        for file in sorted(all_test_files):
            f.write(f"{file}\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file_list> <project_root>")
        sys.exit(1)
    
    file_list = sys.argv[1]
    project_root = sys.argv[2]
    process_files_from_list(file_list, project_root)
    print("Analysis completed. Results written to:")
    print("- test_files_map.json: map of source files to their test files")
    print("- all_test_files.txt: list of all related test files")