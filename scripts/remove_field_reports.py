#!/usr/bin/env python3
"""
Script to comment out field report related code for MVP.
Field reports are postponed to post-MVP.
"""

import re
from pathlib import Path

def comment_lines(filepath, line_ranges):
    """Comment out specific line ranges in a file."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    for start, end in line_ranges:
        for i in range(start - 1, min(end, len(lines))):
            if not lines[i].strip().startswith('#'):
                lines[i] = '# ' + lines[i]
    
    with open(filepath, 'w') as f:
        f.writelines(lines)
    print(f"✓ Commented lines in {filepath}")

def comment_field_report_sections():
    """Comment out all field report related code."""
    
    base_path = Path(__file__).parent.parent
    
    # 1. router.py - Comment field report operations
    router_file = base_path / "src/rails/router.py"
    if router_file.exists():
        print(f"Processing {router_file}...")
        # We'll need to be more surgical here - comment specific dictionary entries
        with open(router_file, 'r') as f:
            content = f.read()
        
        # Comment out field_reports in OPERATIONS dictionary
        content = re.sub(
            r'(\s+"field_reports":\s*\{[^}]+\}),?',
            lambda m: '# ' + m.group(1).replace('\n', '\n# '),
            content,
            flags=re.MULTILINE | re.DOTALL
        )
        
        with open(router_file, 'w') as f:
            f.write(content)
        print(f"✓ Commented field_reports in {router_file}")
    
    # 2. dynamic_prompts.py - Comment field report prompts
    prompts_file = base_path / "src/rails/dynamic_prompts.py"
    if prompts_file.exists():
        comment_lines(prompts_file, [
            (54, 60),   # Field report operation definitions
            (190, 193), # Field report function mappings
            (432, 435), # Duplicate field report function mappings
        ])
    
    # 3. confidence_scoring.py - Comment field report scoring
    scoring_file = base_path / "src/rails/confidence_scoring.py"
    if scoring_file.exists():
        comment_lines(scoring_file, [
            (201, 203), # Field report context pattern matching
            (294, 295), # Field report parameter definitions
            (310, 310), # Field report entity names
            (326, 327), # Field report site extraction confidence
        ])
    
    # 4. production_logger.py - Comment field report entity type
    logger_file = base_path / "src/monitoring/production_logger.py"
    if logger_file.exists():
        comment_lines(logger_file, [(261, 261)])
    
    print("\n✅ Field report code has been commented out")
    print("\nNext steps:")
    print("1. Add @pytest.mark.skip decorators to field report tests")
    print("2. Run tests to verify tasks and lists still work")
    print("3. Test bot with /t and /l commands")

def add_skip_decorators_to_tests():
    """Add skip decorators to field report tests."""
    base_path = Path(__file__).parent.parent
    
    test_files = [
        ("tests/integration/test_e2e_webhook_to_db.py", [
            "test_field_report_creation",
            "test_field_report_with_items"
        ]),
        ("tests/integration/test_smart_rails_integration_proper.py", [
            "test_field_report_routing",
            "test_field_report_extraction"
        ]),
        ("tests/unit/test_router.py", [
            "test_field_report",
            "test_field_report_patterns"
        ]),
        ("tests/unit/test_smart_rails_proper.py", [
            "test_field_report",
            "test_field_report_confidence"
        ]),
    ]
    
    for filepath, test_names in test_files:
        full_path = base_path / filepath
        if full_path.exists():
            with open(full_path, 'r') as f:
                content = f.read()
            
            for test_name in test_names:
                # Add skip decorator before test methods
                pattern = rf'(\n)([ \t]*)(def {test_name}\([^)]*\):)'
                replacement = r'\1\2@pytest.mark.skip(reason="Field reports postponed to post-MVP")\n\2\3'
                content = re.sub(pattern, replacement, content)
            
            with open(full_path, 'w') as f:
                f.write(content)
            print(f"✓ Added skip decorators to {filepath}")

if __name__ == "__main__":
    print("🔧 Removing field report code for MVP focus...")
    print("=" * 50)
    
    comment_field_report_sections()
    print("\n" + "=" * 50)
    print("🔧 Adding skip decorators to field report tests...")
    add_skip_decorators_to_tests()
    
    print("\n" + "=" * 50)
    print("✅ Field report code removal complete!")
    print("\nRemaining MVP features:")
    print("• Tasks (create, assign, manage)")
    print("• Lists (inventory/resource)")
    print("• Reminders via Telegram")