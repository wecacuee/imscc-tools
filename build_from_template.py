#!/usr/bin/env python3
"""
Build an IMSCC file from a local template folder.

This script:
1. Reads course metadata from course.json (or uses defaults)
2. Reads module organization from modules.json (if present)
3. Parses HTML pages to extract metadata from <!-- CANVAS_META --> comments
4. Converts local links to Canvas format:
   - ../web_resources/file.txt → $IMS-CC-FILEBASE$/web_resources/file.txt
   - page.html → $CANVAS_OBJECT_REFERENCE$/pages/page
5. Generates a complete IMSCC file ready for Canvas import
"""

import os
import json
import re
import argparse
from pathlib import Path
from html.parser import HTMLParser
from imscc import (
    Course, Module, Quiz, Assignment, Rubric,
    MultipleChoiceQuestion, TrueFalseQuestion,
    FillInBlankQuestion, FillInMultipleBlanksQuestion,
    MultipleAnswersQuestion, MultipleDropdownsQuestion,
    MatchingQuestion, NumericalAnswerQuestion,
    FormulaQuestion, EssayQuestion,
    FileUploadQuestion, TextOnlyQuestion
)


def parse_canvas_meta(html_content):
    """
    Extract metadata from HTML comments.
    
    Example:
        <!-- CANVAS_META
        title: My Page Title
        home: true
        -->
    
    Returns:
        dict: Metadata dictionary
    """
    meta = {}
    
    # Find CANVAS_META comment block
    pattern = r'<!--\s*CANVAS_META\s*\n(.*?)\n\s*-->'
    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        meta_text = match.group(1)
        # Parse key: value pairs
        for line in meta_text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Convert string booleans
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                
                meta[key] = value
    
    return meta


def title_to_slug(title):
    """
    Convert a page title to a Canvas-compatible slug.
    Canvas converts titles to lowercase, replaces spaces and special chars with hyphens.
    """
    # Convert to lowercase
    slug = title.lower()
    # Replace spaces and special characters with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars except spaces and hyphens
    slug = re.sub(r'[-\s]+', '-', slug)    # Replace spaces and multiple hyphens with single hyphen
    slug = slug.strip('-')                  # Remove leading/trailing hyphens
    return slug


def convert_links(html_content, page_filename, filename_to_slug_map=None):
    """
    Convert local links to Canvas format.
    
    Conversions:
    - ../web_resources/file.txt → $IMS-CC-FILEBASE$/web_resources/file.txt
    - file.txt (in same dir) → $IMS-CC-FILEBASE$/web_resources/file.txt
    - page.html → $CANVAS_OBJECT_REFERENCE$/pages/page-title-slug
    
    Args:
        html_content: The HTML content to process
        page_filename: Current page filename (for context)
        filename_to_slug_map: Dict mapping filename (without .html) to title slug
    """
    if filename_to_slug_map is None:
        filename_to_slug_map = {}
    
    # Convert file links: ../web_resources/file.ext → $IMS-CC-FILEBASE$/web_resources/file.ext
    html_content = re.sub(
        r'href="\.\.\/web_resources\/([^"]+)"',
        r'href="$IMS-CC-FILEBASE$/web_resources/\1"',
        html_content
    )
    
    # Convert file links: web_resources/file.ext → $IMS-CC-FILEBASE$/web_resources/file.ext
    html_content = re.sub(
        r'href="web_resources\/([^"]+)"',
        r'href="$IMS-CC-FILEBASE$/web_resources/\1"',
        html_content
    )
    
    # Convert src attributes for images/resources too
    html_content = re.sub(
        r'src="\.\.\/web_resources\/([^"]+)"',
        r'src="$IMS-CC-FILEBASE$/web_resources/\1"',
        html_content
    )
    
    html_content = re.sub(
        r'src="web_resources\/([^"]+)"',
        r'src="$IMS-CC-FILEBASE$/web_resources/\1"',
        html_content
    )
    
    # Convert page links: page.html → $CANVAS_OBJECT_REFERENCE$/pages/page-title-slug
    # Match .html links that aren't already converted
    def replace_page_link(match):
        full_href = match.group(0)
        page_ref = match.group(1)
        
        # Skip if it's already a Canvas reference or external link
        if '$' in full_href or 'http://' in full_href or 'https://' in full_href:
            return full_href
        
        # Remove .html extension
        filename_base = page_ref.replace('.html', '')
        
        # Look up the title slug for this filename
        if filename_base in filename_to_slug_map:
            page_slug = filename_to_slug_map[filename_base]
        else:
            # Fallback: use filename as slug (for backwards compatibility)
            page_slug = filename_base
        
        return f'href="$CANVAS_OBJECT_REFERENCE$/pages/{page_slug}"'
    
    html_content = re.sub(
        r'href="([^"]+\.html)"',
        replace_page_link,
        html_content
    )
    
    return html_content


def parse_css(css_content):
    """
    Parse CSS content into a list of rules.
    
    Returns:
        list: List of tuples (selector, declarations_dict)
    """
    rules = []
    
    # Remove comments
    css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    # Match CSS rules: selector { declarations }
    pattern = r'([^{]+)\{([^}]+)\}'
    
    for match in re.finditer(pattern, css_content):
        selector = match.group(1).strip()
        declarations = match.group(2).strip()
        
        # Parse declarations into dict
        styles = {}
        for decl in declarations.split(';'):
            decl = decl.strip()
            if ':' in decl:
                prop, value = decl.split(':', 1)
                styles[prop.strip()] = value.strip()
        
        if styles:
            rules.append((selector, styles))
    
    return rules


class CSSInliner(HTMLParser):
    """HTML parser that applies CSS rules inline and removes link tags."""
    
    def __init__(self, css_rules):
        super().__init__()
        self.css_rules = css_rules
        self.output = []
        self.element_stack = []  # Track element hierarchy
    
    def handle_starttag(self, tag, attrs):
        # Skip link tags that reference CSS files
        if tag == 'link':
            attrs_dict = dict(attrs)
            if attrs_dict.get('rel') == 'stylesheet':
                return
        
        # Track element for descendant selectors
        attrs_dict = dict(attrs)
        element_classes = attrs_dict.get('class', '').split()
        element_id = attrs_dict.get('id', '')
        self.element_stack.append((tag, element_id, element_classes))
        
        # Find matching CSS rules and sort by specificity
        matching_rules = []
        for selector, styles in self.css_rules:
            if self._selector_matches(selector):
                specificity = self._calculate_specificity(selector)
                matching_rules.append((specificity, selector, styles))
        
        # Sort by specificity (lower specificity first, so higher overwrites)
        matching_rules.sort(key=lambda x: x[0])
        
        # Apply rules in specificity order
        applicable_styles = {}
        for specificity, selector, styles in matching_rules:
            applicable_styles.update(styles)
        
        # Merge with existing inline styles (inline styles take precedence)
        if applicable_styles:
            existing_style = attrs_dict.get('style', '')
            merged_style = self._merge_styles(existing_style, applicable_styles)
            
            # Update or add style attribute
            new_attrs = []
            style_added = False
            for attr_name, attr_value in attrs:
                if attr_name == 'style':
                    new_attrs.append((attr_name, merged_style))
                    style_added = True
                else:
                    new_attrs.append((attr_name, attr_value))
            
            if not style_added:
                new_attrs.append(('style', merged_style))
            
            attrs = new_attrs
        
        # Reconstruct tag
        attrs_str = ''.join(f' {name}="{value}"' for name, value in attrs)
        self.output.append(f'<{tag}{attrs_str}>')
    
    def handle_endtag(self, tag):
        if tag == 'link':
            return
        
        if self.element_stack and self.element_stack[-1][0] == tag:
            self.element_stack.pop()
        
        self.output.append(f'</{tag}>')
    
    def handle_data(self, data):
        # Escape HTML entities in data
        data = data.replace('&', '&amp;')
        data = data.replace('<', '&lt;')
        data = data.replace('>', '&gt;')
        self.output.append(data)
    
    def handle_entityref(self, name):
        self.output.append(f'&{name};')
    
    def handle_charref(self, name):
        self.output.append(f'&#{name};')
    
    def handle_startendtag(self, tag, attrs):
        if tag == 'link':
            attrs_dict = dict(attrs)
            if attrs_dict.get('rel') == 'stylesheet':
                return
        
        attrs_str = ''.join(f' {name}="{value}"' for name, value in attrs)
        self.output.append(f'<{tag}{attrs_str} />')
    
    def handle_comment(self, data):
        self.output.append(f'<!--{data}-->')
    
    def handle_decl(self, decl):
        self.output.append(f'<!{decl}>')
    
    def _calculate_specificity(self, selector):
        """
        Calculate CSS specificity as a tuple (ids, classes, elements).
        Returns a tuple that can be compared: higher values = higher specificity.
        """
        # Handle comma-separated selectors - use the highest specificity
        if ',' in selector:
            return max(self._calculate_specificity(s.strip()) for s in selector.split(','))
        
        ids = 0
        classes = 0
        elements = 0
        
        # Remove child combinators and split by spaces
        selector_cleaned = selector.replace('>', ' ')
        parts = [p.strip() for p in selector_cleaned.split() if p.strip()]
        
        for part in parts:
            # Count IDs
            ids += part.count('#')
            # Count classes (including pseudo-classes)
            classes += part.count('.')
            classes += part.count('[')  # Attribute selectors
            # Count elements - check if there's a tag name at the START
            # Tag names come before any . # [ : characters
            # Extract tag name (everything before first special char)
            tag_match = re.match(r'^([a-zA-Z][a-zA-Z0-9]*)', part)
            if tag_match:
                elements += 1
        
        return (ids, classes, elements)
    
    def _merge_styles(self, existing_style, new_styles):
        """Merge CSS styles, preferring existing inline styles."""
        existing_dict = {}
        if existing_style:
            for decl in existing_style.split(';'):
                decl = decl.strip()
                if ':' in decl:
                    prop, value = decl.split(':', 1)
                    existing_dict[prop.strip()] = value.strip()
        
        # Merge, preferring existing
        merged = new_styles.copy()
        merged.update(existing_dict)
        
        return '; '.join(f'{prop}: {value}' for prop, value in merged.items())
    
    def _selector_matches(self, selector):
        """Check if selector matches current element."""
        selector = selector.strip()
        
        # Handle comma-separated selectors
        if ',' in selector:
            return any(self._selector_matches(s.strip()) for s in selector.split(','))
        
        # Handle descendant selectors (space-separated)
        if ' ' in selector:
            return self._matches_descendant_selector(selector)
        
        # Single selector
        if not self.element_stack:
            return False
        
        current_tag, current_id, current_classes = self.element_stack[-1]
        return self._matches_simple_selector(selector, current_tag, current_id, current_classes)
    
    def _matches_descendant_selector(self, selector):
        """Match descendant selector like '.parent .child' or '.parent > .child'."""
        # Parse selector parts, keeping track of combinators
        parts = []
        combinators = []
        current_part = []
        
        i = 0
        while i < len(selector):
            char = selector[i]
            if char == '>':
                # Child combinator
                if current_part:
                    parts.append(''.join(current_part).strip())
                    current_part = []
                combinators.append('>')
                i += 1
            elif char == ' ':
                # Descendant combinator (space)
                if current_part:
                    part = ''.join(current_part).strip()
                    if part:
                        parts.append(part)
                        current_part = []
                        # Only add combinator if we actually have a part before the space
                        # and if the last combinator wasn't already added
                        if len(parts) > len(combinators) + 1:
                            combinators.append(' ')
                i += 1
            else:
                current_part.append(char)
                i += 1
        
        # Add final part
        if current_part:
            part = ''.join(current_part).strip()
            if part:
                parts.append(part)
        
        if len(parts) > len(self.element_stack):
            return False
        
        # Check if the last part matches the current element
        current_tag, current_id, current_classes = self.element_stack[-1]
        if not self._matches_simple_selector(parts[-1], current_tag, current_id, current_classes):
            return False
        
        # Work backwards through the selector parts and element stack
        stack_idx = len(self.element_stack) - 2
        
        for i in range(len(parts) - 2, -1, -1):
            selector_part = parts[i]
            combinator = combinators[i] if i < len(combinators) else ' '
            
            if combinator == '>':
                # Child combinator: must match immediate parent only
                if stack_idx < 0:
                    return False
                tag, elem_id, classes = self.element_stack[stack_idx]
                if not self._matches_simple_selector(selector_part, tag, elem_id, classes):
                    return False
                stack_idx -= 1
            else:
                # Descendant combinator: search up the stack
                matched = False
                while stack_idx >= 0:
                    tag, elem_id, classes = self.element_stack[stack_idx]
                    if self._matches_simple_selector(selector_part, tag, elem_id, classes):
                        matched = True
                        stack_idx -= 1
                        break
                    stack_idx -= 1
                
                if not matched:
                    return False
        
        return True
    
    def _matches_simple_selector(self, selector, tag, element_id, element_classes):
        """Match a simple selector against an element."""
        # Handle multiple classes (e.g., .class1.class2 or tag.class1.class2)
        if '.' in selector:
            # Split by dots to get tag (if any) and classes
            parts = selector.split('.')
            tag_part = parts[0] if parts[0] else None
            class_parts = [p for p in parts[1:] if p]
            
            # Check tag if specified
            if tag_part and tag_part != tag:
                return False
            
            # Check all classes are present
            for class_name in class_parts:
                if class_name not in element_classes:
                    return False
            
            return True
        
        # ID selector
        if selector.startswith('#'):
            id_name = selector[1:]
            return element_id == id_name
        
        # Tag with ID
        if '#' in selector:
            tag_part, id_part = selector.split('#', 1)
            return tag == tag_part and element_id == id_part
        
        # Tag selector only
        return selector == tag
    
    def get_output(self):
        return ''.join(self.output)


def inline_css(html_content, template_dir):
    """
    Find and inline CSS files referenced in HTML, then remove the link tags.
    
    Args:
        html_content: HTML content string
        template_dir: Path to template directory
    
    Returns:
        str: HTML with inlined CSS and link tags removed
    """
    # Find CSS file references
    css_link_pattern = r'<link\s+rel="stylesheet"\s+href="([^"]+)"'
    css_files = re.findall(css_link_pattern, html_content, re.IGNORECASE)
    
    if not css_files:
        return html_content
    
    # Load and parse all referenced CSS files
    all_css_rules = []
    for css_file in css_files:
        # Handle relative paths
        css_file_normalized = css_file
        while css_file_normalized.startswith('../'):
            css_file_normalized = css_file_normalized[3:]
        
        css_path = template_dir / css_file_normalized
        if css_path.exists():
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
                rules = parse_css(css_content)
                all_css_rules.extend(rules)
    
    # Apply CSS inline
    inliner = CSSInliner(all_css_rules)
    inliner.feed(html_content)
    
    return inliner.get_output()


def load_course_config(template_dir):
    """Load course configuration from course.json or return defaults."""
    config_path = template_dir / "course.json"
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    
    # Return sensible defaults
    return {
        "title": template_dir.name.replace('-', ' ').replace('_', ' ').title(),
        "course_code": template_dir.name.upper().replace('-', '').replace('_', '')[:20],
        "default_view": "wiki"
    }


def load_modules_config(template_dir):
    """Load module organization from modules.json if it exists."""
    modules_path = template_dir / "modules.json"
    
    if modules_path.exists():
        with open(modules_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('modules', [])
    
    return []


def create_question_from_json(question_data):
    """Create a quiz question object from JSON data."""
    qtype = question_data.get('type')
    text = question_data.get('text', '')
    points = question_data.get('points', 1.0)
    
    if qtype == 'multiple_choice':
        return MultipleChoiceQuestion(
            question_text=text,
            answers=question_data.get('answers', []),
            points_possible=points
        )
    elif qtype == 'true_false':
        return TrueFalseQuestion(
            question_text=text,
            correct_answer=question_data.get('correct_answer', True),
            points_possible=points
        )
    elif qtype == 'fill_in_blank':
        return FillInBlankQuestion(
            question_text=text,
            answers=question_data.get('answers', []),
            points_possible=points
        )
    elif qtype == 'fill_in_multiple_blanks':
        return FillInMultipleBlanksQuestion(
            question_text=text,
            blanks=question_data.get('blanks', {}),
            points_possible=points
        )
    elif qtype == 'multiple_answers':
        return MultipleAnswersQuestion(
            question_text=text,
            answers=question_data.get('answers', []),
            points_possible=points
        )
    elif qtype == 'multiple_dropdowns':
        return MultipleDropdownsQuestion(
            question_text=text,
            dropdowns=question_data.get('dropdowns', {}),
            points_possible=points
        )
    elif qtype == 'matching':
        return MatchingQuestion(
            question_text=text,
            matches=question_data.get('matches', []),
            distractors=question_data.get('distractors', []),
            points_possible=points
        )
    elif qtype == 'numerical_answer':
        return NumericalAnswerQuestion(
            question_text=text,
            exact_answer=question_data.get('exact_answer'),
            answer_range=question_data.get('answer_range'),
            margin=question_data.get('margin', 0.0),
            points_possible=points
        )
    elif qtype == 'formula_question':
        return FormulaQuestion(
            question_text=text,
            formula=question_data.get('formula', ''),
            variables=question_data.get('variables', {}),
            tolerance=question_data.get('tolerance', 0.01),
            points_possible=points
        )
    elif qtype == 'essay_question':
        return EssayQuestion(
            question_text=text,
            points_possible=points
        )
    elif qtype == 'file_upload_question':
        return FileUploadQuestion(
            question_text=text,
            points_possible=points
        )
    elif qtype == 'text_only_question':
        return TextOnlyQuestion(
            question_text=text
        )
    else:
        raise ValueError(f"Unknown question type: {qtype}")


def load_quiz_from_json(quiz_path, identifier=None):
    """Load a quiz from a JSON file."""
    with open(quiz_path, 'r') as f:
        quiz_data = json.load(f)
    
    settings = quiz_data.get('settings', {})
    
    quiz = Quiz(
        title=quiz_data.get('title', 'Untitled Quiz'),
        description=quiz_data.get('description', ''),
        quiz_type=settings.get('quiz_type', 'assignment'),
        identifier=identifier,
        allowed_attempts=settings.get('allowed_attempts', 1),
        scoring_policy=settings.get('scoring_policy', 'keep_highest'),
        shuffle_questions=settings.get('shuffle_questions', False),
        shuffle_answers=settings.get('shuffle_answers', False),
        show_correct_answers=settings.get('show_correct_answers', True),
        one_question_at_a_time=settings.get('one_question_at_a_time', False),
        cant_go_back=settings.get('cant_go_back', False),
        time_limit=settings.get('time_limit')
    )
    
    for question_data in quiz_data.get('questions', []):
        question = create_question_from_json(question_data)
        quiz.add_question(question)
    
    return quiz


def load_assignment_from_json(assignment_path, identifier=None):
    """Load an assignment from a JSON file."""
    with open(assignment_path, 'r', encoding='utf-8') as f:
        assignment_data = json.load(f)
    
    # Handle description_file if specified
    description = assignment_data.get('description', '')
    description_file = assignment_data.get('description_file')
    
    if description_file:
        # Look for the HTML file in the same directory as the JSON file
        html_path = assignment_path.parent / description_file
        if html_path.exists():
            with open(html_path, 'r', encoding='utf-8') as f:
                description = f.read()
            
            # Inline CSS and remove link tags
            description = inline_css(description, assignment_path.parent.parent)
        else:
            print(f"   ⚠️  Warning: Description file '{description_file}' not found for {assignment_path.name}")
    
    # Convert submission_types list to comma-separated string
    submission_types = assignment_data.get('submission_types', ['online_upload'])
    if isinstance(submission_types, list):
        submission_types = ','.join(submission_types)
    
    # Convert allowed_extensions list to comma-separated string
    allowed_extensions = assignment_data.get('allowed_extensions', [])
    if isinstance(allowed_extensions, list):
        allowed_extensions = ','.join(allowed_extensions)
    
    return Assignment(
        title=assignment_data.get('title', 'Untitled Assignment'),
        description=description,
        points_possible=assignment_data.get('points_possible', 100),
        submission_types=submission_types,
        allowed_extensions=allowed_extensions,
        grading_type=assignment_data.get('grading_type', 'points'),
        due_at=assignment_data.get('due_at'),
        unlock_at=assignment_data.get('unlock_at'),
        lock_at=assignment_data.get('lock_at'),
        identifier=identifier
    )


def load_rubric_from_json(rubric_path):
    """Load a rubric from a JSON file."""
    with open(rubric_path, 'r') as f:
        rubric_data = json.load(f)
    
    # Get rubric title from JSON or filename
    rubric_title = rubric_data.get('title')
    if not rubric_title:
        rubric_title = rubric_path.stem.replace('-', ' ').replace('_', ' ').title()
    
    rubric = Rubric(title=rubric_title)
    
    for criterion_data in rubric_data.get('criteria', []):
        rubric.add_criterion(
            description=criterion_data.get('description', 'Criterion'),
            long_description=criterion_data.get('long_description', ''),
            points=criterion_data.get('points', 0),
            ratings=criterion_data.get('ratings', [])
        )
    
    return rubric


def build_imscc(template_dir, output_file=None):
    """Build IMSCC file from template directory."""
    
    template_path = Path(template_dir).resolve()
    
    if not template_path.exists():
        print(f"❌ Error: Directory '{template_dir}' does not exist!")
        return False
    
    wiki_dir = template_path / "wiki_content"
    files_dir = template_path / "web_resources"
    
    if not wiki_dir.exists():
        print(f"❌ Error: No 'wiki_content' folder found in '{template_dir}'")
        print(f"   Expected structure:")
        print(f"     {template_dir}/")
        print(f"     ├── wiki_content/")
        print(f"     └── web_resources/")
        return False
    
    print("\n" + "=" * 70)
    print(f"Building IMSCC from Template: {template_path.name}")
    print("=" * 70)
    
    # Load configuration
    print("\n⚙️  Loading configuration...")
    config = load_course_config(template_path)
    modules_config = load_modules_config(template_path)
    
    print(f"   Course Title: {config['title']}")
    print(f"   Course Code: {config['course_code']}")
    print(f"   Default View: {config.get('default_view', 'wiki')}")
    
    # Create course
    course = Course(
        title=config['title'],
        course_code=config['course_code'],
        default_view=config.get('default_view', 'wiki')
    )
    
    # Process pages
    print(f"\n📄 Processing pages from {wiki_dir.name}/...")
    
    html_files = sorted(wiki_dir.glob("**/*.html")) + sorted(wiki_dir.glob("**/*.cs"))
    if not html_files:
        print(f"   ⚠️  No HTML files found in {wiki_dir}")
    
    # First pass: Build filename → title slug mapping
    filename_to_slug_map = {}
    for html_file in html_files:
        html_content = html_file.read_text(encoding='utf-8')
        meta = parse_canvas_meta(html_content)
        
        filename_base = html_file.stem
        page_title = meta.get('title', filename_base.replace('-', ' ').replace('_', ' ').title())
        title_slug = title_to_slug(page_title)
        
        filename_to_slug_map[filename_base] = title_slug
    
    # Second pass: Process pages with correct link mapping
    pages_map = {}  # Map page slug to page object
    home_page = None
    
    for html_file in html_files:
        # Read HTML content
        html_content = html_file.read_text(encoding='utf-8')
        
        # Inline CSS and remove link tags
        html_content = inline_css(html_content, template_path)
        
        # Parse metadata
        meta = parse_canvas_meta(html_content)
        
        # Determine page title
        filename_base = html_file.stem
        page_title = meta.get('title', filename_base.replace('-', ' ').replace('_', ' ').title())
        title_slug = title_to_slug(page_title)
        
        # Convert links using the filename→slug map
        converted_html = convert_links(html_content, html_file.name, filename_to_slug_map)
        
        # Remove the CANVAS_META comment from final output
        converted_html = re.sub(
            r'<!--\s*CANVAS_META\s*\n.*?\n\s*-->',
            '',
            converted_html,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # Extract body content if full HTML document
        head_match = re.search(r'<head[^>]*>(.*?)</head>', converted_html, re.DOTALL | re.IGNORECASE)
        if head_match:
            previous_head = head_match.group(1).strip()
        else:
            previous_head = ""
        body_match = re.search(r'<body[^>]*>(.*?)</body>', converted_html, re.DOTALL | re.IGNORECASE)
        if body_match:
            converted_html = body_match.group(1).strip()
        
        # Check if this is the home page
        is_home = meta.get('home') in ('true', 'True', True, '1', 1)
        
        # Add page to course
        page = course.add_page(
            title=page_title,
            content=converted_html,
            is_front_page=is_home,
            previous_head=previous_head
        )
        
        pages_map[title_slug] = page
        
        # Track home page
        if is_home:
            home_page = page
        
        print(f"   ✓ {page_title} ({html_file.name}){' [HOME]' if meta.get('home') else ''}")
    
    # Process files
    if files_dir.exists():
        print(f"\n📎 Processing files from {files_dir.name}/...")
        
        # Get all files recursively
        all_files = []
        for root, dirs, files in os.walk(files_dir):
            for file in files:
                if not file.startswith('.'):  # Skip hidden files
                    filepath = Path(root) / file
                    all_files.append(filepath)
        
        if not all_files:
            print(f"   ℹ️  No files found in {files_dir}")
        
        for filepath in sorted(all_files):
            # Calculate relative path from web_resources
            rel_path = filepath.relative_to(files_dir)
            destination = f"web_resources/{rel_path}"
            
            course.add_file(str(filepath), destination)
            print(f"   ✓ {rel_path}")
    
    # Process rubrics
    rubrics_dir = template_path / "rubrics"
    rubrics_map = {}  # Map rubric filename (without .json) to rubric object
    
    if rubrics_dir.exists():
        print(f"\n📊 Processing rubrics from {rubrics_dir.name}/...")
        
        json_files = sorted(rubrics_dir.glob("*.json"))
        if not json_files:
            print(f"   ℹ️  No JSON files found in {rubrics_dir}")
        
        for json_file in json_files:
            rubric_id = json_file.stem
            try:
                rubric = load_rubric_from_json(json_file)
                if rubric:
                    rubrics_map[rubric_id] = rubric
                    course.add_rubric(rubric)
                    print(f"   ✓ {rubric.title} ({json_file.name})")
            except Exception as e:
                print(f"   ❌ Error loading {json_file.name}: {e}")
    
    # Process quizzes
    quizzes_dir = template_path / "quizzes"
    quizzes_map = {}  # Map quiz filename (without .json) to quiz object
    
    if quizzes_dir.exists():
        print(f"\n📝 Processing quizzes from {quizzes_dir.name}/...")
        
        quiz_files = sorted(quizzes_dir.glob("*.json"))
        if not quiz_files:
            print(f"   ℹ️  No JSON files found in {quizzes_dir}")
        
        for quiz_file in quiz_files:
            quiz_id = quiz_file.stem
            try:
                quiz = load_quiz_from_json(quiz_file, identifier=quiz_id)
                quizzes_map[quiz_id] = quiz
                course.add_quiz(quiz)
                num_questions = len(quiz.questions)
                total_points = sum(q.points_possible for q in quiz.questions)
                print(f"   ✓ {quiz.title} ({num_questions} questions, {total_points} points)")
            except Exception as e:
                print(f"   ❌ Error loading {quiz_file.name}: {e}")
    
    # Process assignments
    assignments_dir = template_path / "assignments"
    assignments_map = {}  # Map assignment filename (without .json) to assignment object
    
    if assignments_dir.exists():
        print(f"\n📋 Processing assignments from {assignments_dir.name}/...")
        
        assignment_files = sorted(assignments_dir.glob("*.json"))
        if not assignment_files:
            print(f"   ℹ️  No JSON files found in {assignments_dir}")
        
        for assignment_file in assignment_files:
            assignment_id = assignment_file.stem
            try:
                with open(assignment_file, 'r') as f:
                    assignment_data = json.load(f)
                
                assignment = load_assignment_from_json(assignment_file, identifier=assignment_id)
                
                # Attach rubric if specified
                rubric_ref = assignment_data.get('rubric')
                if rubric_ref and rubric_ref in rubrics_map:
                    assignment.attach_rubric(rubrics_map[rubric_ref])
                
                # Set assignment group if specified
                group_name = assignment_data.get('assignment_group')
                if group_name:
                    # Get or create assignment group
                    assignment.assignment_group_identifierref = course.create_assignment_group(
                        title=group_name
                    ).identifier
                
                assignments_map[assignment_id] = assignment
                course.add_assignment(assignment)
                print(f"   ✓ {assignment.title} ({assignment.points_possible} points)")
            except Exception as e:
                print(f"   ❌ Error loading {assignment_file.name}: {e}")
    
    # Process modules
    if modules_config:
        print(f"\n📚 Creating modules...")
        
        for module_config in modules_config:
            module_title = module_config.get('title', 'Untitled Module')
            module = course.create_module(module_title)
            
            # Support both old format (pages) and new format (items)
            items = module_config.get('items', [])
            
            # Backwards compatibility: convert old 'pages' format to new 'items' format
            if not items and 'pages' in module_config:
                items = [{'type': 'page', 'id': page_id} for page_id in module_config['pages']]
            
            item_count = 0
            for item in items:
                item_type = item.get('type')
                item_id = item.get('id') or item.get('identifier')  # Support both 'id' and 'identifier'
                
                if item_type == 'page':
                    # Convert filename to title slug
                    if item_id in filename_to_slug_map:
                        title_slug = filename_to_slug_map[item_id]
                        if title_slug in pages_map:
                            module.add_page(pages_map[title_slug])
                            item_count += 1
                        else:
                            print(f"   ⚠️  Warning: Page '{item_id}' (slug: {title_slug}) not found")
                    else:
                        print(f"   ⚠️  Warning: Page '{item_id}' not found")
                
                elif item_type == 'quiz':
                    if item_id in quizzes_map:
                        module.add_quiz(quizzes_map[item_id])
                        item_count += 1
                    else:
                        print(f"   ⚠️  Warning: Quiz '{item_id}' not found")
                
                elif item_type == 'assignment':
                    if item_id in assignments_map:
                        module.add_assignment(assignments_map[item_id])
                        item_count += 1
                    else:
                        print(f"   ⚠️  Warning: Assignment '{item_id}' not found")
                
                else:
                    print(f"   ⚠️  Warning: Unknown item type '{item_type}' for '{item_id}'")
            
            print(f"   ✓ {module_title} ({item_count} items)")
    
    # Determine output filename
    if output_file is None:
        output_file = f"{config['course_code']}.imscc"
    
    # Export
    print(f"\n💾 Exporting to {output_file}...")
    course.export(output_file)
    
    # Get file size
    file_size = os.path.getsize(output_file)
    file_size_kb = file_size / 1024
    
    # Success
    print("\n" + "=" * 70)
    print("✅ IMSCC File Created Successfully!")
    print("=" * 70)
    
    print(f"\n📊 Summary:")
    print(f"   Output File: {output_file}")
    print(f"   File Size: {file_size:,} bytes ({file_size_kb:.1f} KB)")
    print(f"   Pages: {len(pages_map)}")
    print(f"   Files: {len(all_files) if files_dir.exists() and all_files else 0}")
    print(f"   Quizzes: {len(quizzes_map)}")
    print(f"   Assignments: {len(assignments_map)}")
    print(f"   Rubrics: {len(rubrics_map)}")
    print(f"   Modules: {len(modules_config)}")
    
    if home_page:
        print(f"   Home Page: {home_page.title}")
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Go to your Canvas course")
    print(f"   2. Settings → Import Course Content")
    print(f"   3. Choose 'Common Cartridge 1.x Package'")
    print(f"   4. Upload {output_file}")
    print(f"   5. Select content and import")
    
    print(f"\n💡 All local links have been converted to Canvas format:")
    print(f"   • File links: $IMS-CC-FILEBASE$/web_resources/...")
    print(f"   • Page links: $CANVAS_OBJECT_REFERENCE$/pages/...\n")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Build IMSCC file from a local template folder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 build_from_template.py my-course
  python3 build_from_template.py biology-101 -o bio101.imscc
  python3 build_from_template.py . 

Template Structure:
  my-course/
  ├── wiki_content/          # HTML pages (required)
  │   ├── welcome.html
  │   └── lesson-1.html
  ├── web_resources/         # Files (optional)
  │   └── syllabus.pdf
  ├── course.json           # Course metadata (optional)
  └── modules.json          # Module organization (optional)

Page Metadata (in HTML comments):
  <!-- CANVAS_META
  title: My Page Title
  home: true
  -->

Link Conversion:
  Local: <a href="../web_resources/file.txt">File</a>
  Canvas: <a href="$IMS-CC-FILEBASE$/web_resources/file.txt">File</a>
  
  Local: <a href="page.html">Page</a>
  Canvas: <a href="$CANVAS_OBJECT_REFERENCE$/pages/page">Page</a>
        """
    )
    
    parser.add_argument(
        'template_dir',
        help='Path to the template directory (or . for current directory)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output IMSCC filename (default: COURSECODE.imscc)',
        default=None
    )
    
    args = parser.parse_args()
    
    build_imscc(args.template_dir, args.output)


if __name__ == '__main__':
    main()
