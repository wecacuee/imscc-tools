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
        with open(modules_path, 'r') as f:
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


def load_quiz_from_json(quiz_path):
    """Load a quiz from a JSON file."""
    with open(quiz_path, 'r') as f:
        quiz_data = json.load(f)
    
    settings = quiz_data.get('settings', {})
    
    quiz = Quiz(
        title=quiz_data.get('title', 'Untitled Quiz'),
        description=quiz_data.get('description', ''),
        quiz_type=settings.get('quiz_type', 'assignment'),
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


def load_assignment_from_json(assignment_path):
    """Load an assignment from a JSON file."""
    with open(assignment_path, 'r') as f:
        assignment_data = json.load(f)
    
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
        description=assignment_data.get('description', ''),
        points_possible=assignment_data.get('points_possible', 100),
        submission_types=submission_types,
        allowed_extensions=allowed_extensions,
        grading_type=assignment_data.get('grading_type', 'points'),
        due_at=assignment_data.get('due_at'),
        unlock_at=assignment_data.get('unlock_at'),
        lock_at=assignment_data.get('lock_at')
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


def load_modules_config(template_dir):
    """Load module organization from modules.json if it exists."""
    modules_path = template_dir / "modules.json"
    
    if modules_path.exists():
        with open(modules_path, 'r') as f:
            return json.load(f).get('modules', [])
    
    return []


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
    
    html_files = sorted(wiki_dir.glob("*.html"))
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
        
        # Add page to course
        page = course.add_page(
            title=page_title,
            content=converted_html
        )
        
        pages_map[title_slug] = page
        
        # Track home page
        if meta.get('home'):
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
                quiz = load_quiz_from_json(quiz_file)
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
                
                assignment = load_assignment_from_json(assignment_file)
                
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
                item_id = item.get('id')
                
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
