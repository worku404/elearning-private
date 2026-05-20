#!/usr/bin/env python3
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edu.settings.production')
django.setup()

from courses.templatetags.course_markdown import markdown_filter

# Test inline code
test_markdown = "Here is some `inline_code`:\n\n| Type | Description |\n|------|-------------|  \n| INT | Whole number |"
result = markdown_filter(test_markdown)
print("=== RENDERED HTML ===")
print(result)
print("\n=== Checking for <code> tags ===")
if '<code>' in result:
    print("✓ <code> tags are present")
else:
    print("✗ <code> tags are MISSING")
print("\n=== Checking for <table> tags ===")
if '<table>' in result:
    print("✓ <table> tags are present")
else:
    print("✗ <table> tags are MISSING")
