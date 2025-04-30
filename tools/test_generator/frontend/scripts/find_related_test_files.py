#!/usr/bin/env python3
"""
Script to find test files related to frontend source files (JS, TS, Svelte).
Usage: python find_related_test_files.py <file_list> <project_root>

Example:
    python find_related_test_files.py frontend_relevant_files.txt /path/to/workspace/frontend
"""

import os
import sys
import json
import re
from pathlib import Path
from collections import defaultdict


def normalize_path(path):
    """Normalize a file path to make it consistent for comparison."""
    return str(Path(path).resolve())


def is_test_file(file_path):
    """Check if the file is a test file."""
    file_name = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    
    # Check if the file has test indicators in the name
    name_indicators = (
        file_name.startswith("test_") or 
        file_name.endswith(".test.js") or 
        file_name.endswith(".test.ts") or 
        file_name.endswith(".test.svelte") or
        file_name.endswith(".spec.js") or 
        file_name.endswith(".spec.ts") or 
        file_name.endswith(".spec.svelte")
    )
    
    # Check if the file is in a test directory
    dir_indicators = (
        "/tests/" in file_path or 
        "/test/" in file_path or 
        "/__tests__/" in file_path or
        file_dir.endswith("/tests") or 
        file_dir.endswith("/test") or 
        file_dir.endswith("/__tests__")
    )
    
    return name_indicators or dir_indicators


def extract_imports(test_file_path):
    """Extract import statements from a test file to analyze dependencies."""
    try:
        with open(test_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        imports = []
        
        # For Svelte files, extract script content first
        if test_file_path.endswith('.svelte'):
            # Match script tags
            script_matches = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
            content = '\n'.join(script_matches) if script_matches else content
        
        # Match different import patterns
        
        # ES6 imports (import X from 'Y')
        es6_imports = re.findall(r'''
            import\s+                           # import keyword with whitespace
            (?:(?:\w+)|(?:{[^}]+})|(?:\*\s+as\s+\w+))  # import name patterns
            \s+from\s+                          # from keyword
            ['"]([^'"]+)['"]                    # module path
        ''', content, re.VERBOSE)
        imports.extend(es6_imports)
        
        # Side-effect imports (import 'Y')
        side_effect_imports = re.findall(r'''
            import\s+['"]([^'"]+)['"]          # import 'module'
        ''', content, re.VERBOSE)
        imports.extend(side_effect_imports)
        
        # Export from (export ... from 'Y')
        export_imports = re.findall(r'''
            export\s+                           # export keyword
            (?:(?:\w+)|(?:{[^}]+})|(?:\*))      # export patterns
            \s+from\s+                          # from keyword
            ['"]([^'"]+)['"]                    # module path
        ''', content, re.VERBOSE)
        imports.extend(export_imports)
        
        # Dynamic imports (import('Y'))
        dynamic_imports = re.findall(r'''
            import\(\s*['"]([^'"]+)['"]\s*\)    # dynamic import
        ''', content, re.VERBOSE)
        imports.extend(dynamic_imports)
        
        # CommonJS require (require('Y'))
        require_imports = re.findall(r'''
            require\(\s*['"]([^'"]+)['"]\s*\)    # require import
        ''', content, re.VERBOSE)
        imports.extend(require_imports)
        
        return list(set(imports))  # Remove duplicates
    
    except Exception as e:
        print(f"Error extracting imports from {test_file_path}: {e}", file=sys.stderr)
        return []


def check_import_references_file(test_file_path, source_file_path, workspace_dir):
    """Check if a test file imports the source file."""
    # Normalize paths for comparison
    normalized_source = normalize_path(os.path.join(workspace_dir, source_file_path))
    
    # Get the source file name and base name (without extension)
    source_file_name = os.path.basename(source_file_path)
    source_base_name, _ = os.path.splitext(source_file_name)
    
    # Get the source file directory path (relative to workspace)
    source_dir_path = os.path.dirname(source_file_path)
    
    # Extract import statements from test file
    imports = extract_imports(test_file_path)
    
    for import_path in imports:
        # Handle relative imports and resolve them
        if import_path.startswith('.'):
            test_file_dir = os.path.dirname(test_file_path)
            # Try to resolve the relative import to an absolute path
            resolved_import = os.path.normpath(os.path.join(test_file_dir, import_path))
            
            # Try with different extensions if no extension in import
            if not os.path.splitext(import_path)[1]:
                for ext in ['.js', '.ts', '.svelte', '.jsx', '.tsx']:
                    possible_path = f"{resolved_import}{ext}"
                    if os.path.exists(possible_path) and normalize_path(possible_path) == normalized_source:
                        return True
            
            # Check if the resolved path matches our source file
            if os.path.exists(resolved_import) and normalize_path(resolved_import) == normalized_source:
                return True
        
        # Check for aliases like '$lib/components/Button' -> 'src/lib/components/Button'
        elif import_path.startswith('$'):
            alias_path = import_path.replace('$lib/', 'src/lib/')
            alias_path = alias_path.replace('$components/', 'src/components/')
            alias_path = alias_path.replace('$routes/', 'src/routes/')
            alias_path = alias_path.replace('$stores/', 'src/stores/')
            
            full_alias_path = os.path.join(workspace_dir, alias_path)
            
            # Try with different extensions if no extension in import
            if not os.path.splitext(import_path)[1]:
                for ext in ['.js', '.ts', '.svelte', '.jsx', '.tsx']:
                    possible_path = f"{full_alias_path}{ext}"
                    if os.path.exists(possible_path) and normalize_path(possible_path) == normalized_source:
                        return True
            
            # Check direct match
            if os.path.exists(full_alias_path) and normalize_path(full_alias_path) == normalized_source:
                return True
        
        # Check content-based reference (search for component name or file path)
        # Open the test file and check if it references the component by name
        try:
            with open(test_file_path, 'r', encoding='utf-8') as file:
                content = file.read().lower()
                
                # Convert kebab-case or snake_case to camelCase and PascalCase for component matching
                component_names = []
                
                # Original name
                component_names.append(source_base_name.lower())
                
                # If kebab case (my-component), convert to camelCase and PascalCase
                if '-' in source_base_name:
                    words = source_base_name.split('-')
                    camel_case = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
                    pascal_case = ''.join(word.capitalize() for word in words)
                    component_names.extend([camel_case.lower(), pascal_case.lower()])
                
                # If snake case (my_component), convert to camelCase and PascalCase
                if '_' in source_base_name:
                    words = source_base_name.split('_')
                    camel_case = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
                    pascal_case = ''.join(word.capitalize() for word in words)
                    component_names.extend([camel_case.lower(), pascal_case.lower()])
                
                # Check each possible component name
                for name in component_names:
                    # Check for common patterns in tests
                    if any(pattern.format(name=name) in content for pattern in [
                        "import {{\s*{name}\s*}}",
                        "import {name}",
                        "const {name}",
                        "let {name}",
                        "class {name}",
                        "<{name}",
                        "render\({name}",
                        "mount\({name}",
                        "test\(['\"].*{name}.*['\"]",
                        "describe\(['\"].*{name}.*['\"]"
                    ]):
                        return True
                
                # Check if the source directory name is referenced in the test
                source_dir_name = os.path.basename(source_dir_path).lower()
                if source_dir_name and len(source_dir_name) > 2:  # Avoid very short directory names
                    if source_dir_name in content:
                        return True
                        
        except Exception as e:
            print(f"Error reading test file {test_file_path} for content analysis: {e}", file=sys.stderr)
    
    return False


def find_direct_test_file(file_path, workspace_dir):
    """Find the test files that directly test the given file."""
    direct_test_files = []
    
    # Get the file name without extension
    file_path = file_path.strip()
    file_name = os.path.basename(file_path)
    name_without_ext, ext = os.path.splitext(file_name)
    
    # Make sure we have the full path of the source file
    full_source_path = os.path.join(workspace_dir, file_path)
    if not os.path.exists(full_source_path):
        print(f"Warning: Could not find source file at: {full_source_path}")
        return []
    
    # Get source file directory
    source_dir = os.path.dirname(full_source_path)
    
    # Common test file naming patterns
    test_patterns = [
        f"{name_without_ext}.test{ext}",  # component.test.js
        f"{name_without_ext}.spec{ext}",  # component.spec.js
        f"test_{name_without_ext}{ext}",  # test_component.js
        f"{name_without_ext}.test.js",    # component.test.js (for any file type)
        f"{name_without_ext}.spec.js",    # component.spec.js (for any file type)
        f"{name_without_ext}.test.ts",    # component.test.ts (for any file type)
        f"{name_without_ext}.spec.ts",    # component.spec.ts (for any file type)
    ]
    
    # Common test locations relative to the source file
    relative_test_locations = [
        os.path.join(source_dir),                 # Same directory
        os.path.join(source_dir, "__tests__"),    # __tests__ subdirectory
        os.path.join(source_dir, "tests"),        # tests subdirectory
        os.path.join(source_dir, "test"),         # test subdirectory
    ]
    
    # Common test locations elsewhere in the project
    project_test_locations = []
    
    # If file is in src/components, look in test/components
    if "src/components" in file_path:
        component_test_dir = file_path.replace("src/components", "tests/components")
        component_test_dir = os.path.dirname(os.path.join(workspace_dir, component_test_dir))
        project_test_locations.append(component_test_dir)
    
    # If file is in src/routes, look in test/routes
    if "src/routes" in file_path:
        route_test_dir = file_path.replace("src/routes", "tests/routes")
        route_test_dir = os.path.dirname(os.path.join(workspace_dir, route_test_dir))
        project_test_locations.append(route_test_dir)
    
    # Check for tests in the same directory structure but under the tests directory
    if "src/" in file_path:
        main_test_dir = file_path.replace("src/", "tests/")
        main_test_dir = os.path.dirname(os.path.join(workspace_dir, main_test_dir))
        project_test_locations.append(main_test_dir)
    
    # Add the main tests directory
    project_test_locations.append(os.path.join(workspace_dir, "tests"))
    
    # Add e2e and unit test directories
    project_test_locations.append(os.path.join(workspace_dir, "tests", "e2e"))
    project_test_locations.append(os.path.join(workspace_dir, "tests", "unit"))
    
    # First, check for test files in relative locations using naming patterns
    for test_dir in relative_test_locations:
        if os.path.exists(test_dir):
            for pattern in test_patterns:
                potential_test_file = os.path.join(test_dir, pattern)
                if os.path.exists(potential_test_file):
                    direct_test_files.append(potential_test_file)
    
    # Then, check for test files in project test locations using naming patterns
    for test_dir in project_test_locations:
        if os.path.exists(test_dir):
            for pattern in test_patterns:
                potential_test_file = os.path.join(test_dir, pattern)
                if os.path.exists(potential_test_file):
                    direct_test_files.append(potential_test_file)
    
    # If we haven't found any tests by filename pattern, search for tests that may reference the source file
    if not direct_test_files:
        # Find all test files in the project
        all_test_files = []
        for root, _, files in os.walk(os.path.join(workspace_dir, "tests")):
            for file in files:
                if file.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts")):
                    all_test_files.append(os.path.join(root, file))
        
        # Also check for tests in the source directory
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts")):
                    all_test_files.append(os.path.join(root, file))
        
        # Check if any of these tests reference our source file
        for test_file in all_test_files:
            if check_import_references_file(test_file, file_path, workspace_dir):
                direct_test_files.append(test_file)
    
    # Convert to relative paths
    relative_test_files = []
    for test_file in direct_test_files:
        try:
            rel_path = os.path.relpath(test_file, workspace_dir)
            relative_test_files.append(rel_path)
        except ValueError:
            # Keep absolute path if relative path can't be determined
            relative_test_files.append(test_file)
    
    return list(set(relative_test_files))  # Remove duplicates


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file_with_list_of_files> <workspace_dir>")
        sys.exit(1)
    
    input_file_path = sys.argv[1]
    workspace_dir = sys.argv[2]
    
    all_test_files = []
    file_to_tests_map = {}
    source_files_list = []
    
    try:
        # Read the list of files
        with open(input_file_path, 'r') as file_list:
            for line in file_list:
                file_path = line.strip()
                if file_path:
                    # Keep track of all source files
                    source_files_list.append(file_path)
                    
                    # Skip files that are already test files
                    if is_test_file(file_path):
                        # Normalize test file path
                        full_test_path = os.path.join(workspace_dir, file_path)
                        if os.path.exists(full_test_path):
                            rel_test_path = os.path.relpath(full_test_path, workspace_dir)
                            all_test_files.append(rel_test_path)
                            file_to_tests_map[file_path] = [rel_test_path]  # Test file maps to itself
                        continue
                    
                    # Find direct test files
                    test_files = find_direct_test_file(file_path, workspace_dir)
                    if test_files:
                        file_to_tests_map[file_path] = test_files
                        all_test_files.extend(test_files)
                    else:
                        # If no test files found, include an empty list in the mapping
                        file_to_tests_map[file_path] = []
        
        # Remove duplicates while preserving order
        unique_test_files = []
        for file in all_test_files:
            if file not in unique_test_files:
                unique_test_files.append(file)
        
        # Write the list of test files
        with open('all_test_files.txt', 'w') as output_file:
            for test_file in unique_test_files:
                output_file.write(f"{test_file}\n")
        
        # Write the mapping for debugging/reference
        with open('test_files_mapping.json', 'w') as mapping_file:
            json.dump(file_to_tests_map, mapping_file, indent=2)
        
        # Write the related tests mapping (includes files with no tests)
        # This ensures all source files are included in the JSON even if they have no tests
        related_tests_map = {}
        for source_file in source_files_list:
            related_tests_map[source_file] = file_to_tests_map.get(source_file, [])
        
        with open('related_tests.json', 'w') as related_tests_file:
            json.dump(related_tests_map, related_tests_file, indent=2)
        
        print(f"Found {len(unique_test_files)} test files related to {len(source_files_list)} source files.")
        print(f"Wrote results to:")
        print(f"  - all_test_files.txt")
        print(f"  - test_files_mapping.json")
        print(f"  - related_tests.json")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()