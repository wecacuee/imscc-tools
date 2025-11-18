#!/usr/bin/env python3
"""
Create a template folder structure for working on Canvas course content locally.

The template mirrors the IMSCC structure:
- wiki_content/ - HTML pages
- web_resources/ - Files (PDFs, images, etc.)
- course.json - Course metadata (optional)
- modules.json - Module organization (optional)

Pages use HTML comments for metadata:
  <!-- CANVAS_META
  title: Page Title
  home: true
  -->

Links work locally and are converted to Canvas format during IMSCC export.
"""

import os
import json
import argparse
from pathlib import Path


EXAMPLE_PAGE_WITH_FILE_LINK = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome to Your Course</title>
</head>
<body>
<!-- CANVAS_META
title: Welcome (TEMPLATE)
home: true
-->

<h1>🎓 Welcome to Your Course Template!</h1>

<p>This is a <strong>comprehensive example template</strong> that demonstrates all available features. You can edit these HTML files directly and preview them in your browser.</p>

<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Template Files:</strong> All example files are tagged with <code>_TEMPLATE</code> in their filenames. You can easily identify and remove them later:
    <ul>
        <li>Delete files ending in <code>_TEMPLATE.html</code>, <code>_TEMPLATE.txt</code>, or <code>_TEMPLATE.json</code></li>
        <li>Or keep them as reference while building your course</li>
    </ul>
</div>

<h2>📄 Course Documents</h2>
<p>Example file links:</p>
<ul>
    <li><a href="../web_resources/syllabus_TEMPLATE.txt">Course Syllabus</a></li>
    <li><a href="../web_resources/week1-reading_TEMPLATE.txt">Week 1 Reading</a></li>
    <li><a href="../web_resources/resources_TEMPLATE.txt">Additional Resources</a></li>
</ul>

<h2>📚 Course Pages</h2>
<p>Continue to <a href="lesson-1_TEMPLATE.html">Lesson 1</a> to see more examples.</p>

<h2>✨ What's Included</h2>
<ul>
    <li><strong>Comprehensive Quiz:</strong> Demonstrates all 12 question types (multiple choice, true/false, fill-in-blank, essay, file upload, and more)</li>
    <li><strong>Assignment Example:</strong> Shows submission types, file restrictions, and rubric integration</li>
    <li><strong>Detailed Rubric:</strong> 5 criteria with 5 rating levels each, including long descriptions</li>
    <li><strong>Working Links:</strong> All file and page links work locally for easy previewing</li>
</ul>

<div style="background-color: #f0f0f0; padding: 15px; margin-top: 20px; border-left: 4px solid #0374B5;">
    <strong>📖 How Links Work:</strong>
    <ul>
        <li>File links like <code>../web_resources/file.txt</code> will become <code>$IMS-CC-FILEBASE$/web_resources/file.txt</code></li>
        <li>Page links like <code>lesson-1_TEMPLATE.html</code> will become <code>$CANVAS_OBJECT_REFERENCE$/pages/lesson-1_TEMPLATE</code></li>
    </ul>
    <p>This happens automatically when you export to IMSCC format!</p>
</div>

</body>
</html>
"""

EXAMPLE_LESSON_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Lesson 1</title>
</head>
<body>
<!-- CANVAS_META
title: Lesson 1: Getting Started (TEMPLATE)
-->

<h1>📖 Lesson 1: Getting Started</h1>

<p>This is an example lesson page showing how to structure your course content.</p>

<h2>📚 Reading Materials</h2>
<p>Review these documents before proceeding:</p>
<ul>
    <li><a href="../web_resources/syllabus_TEMPLATE.txt">Course Syllabus</a> - Course overview and policies</li>
    <li><a href="../web_resources/week1-reading_TEMPLATE.txt">Week 1 Reading</a> - Required reading for this week</li>
</ul>

<h2>🎯 Learning Objectives</h2>
<p>By the end of this lesson, you will be able to:</p>
<ol>
    <li>Understand the course structure and expectations</li>
    <li>Navigate between pages and access course resources</li>
    <li>Submit assignments and take quizzes</li>
</ol>

<h2>🔗 Navigation</h2>
<p>
    ← <a href="welcome_TEMPLATE.html">Back to Welcome</a> |
    <a href="lesson-2_TEMPLATE.html">Next: Lesson 2</a> →
</p>

<div style="background-color: #e7f3ff; padding: 15px; margin-top: 20px; border-left: 4px solid #2196F3;">
    <strong>💡 Tip:</strong> This is a template file. You can delete it later by removing files with <code>_TEMPLATE</code> in the name.
</div>

</body>
</html>
"""

EXAMPLE_LESSON_2_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Lesson 2</title>
</head>
<body>
<!-- CANVAS_META
title: Lesson 2: Core Concepts (TEMPLATE)
-->

<h1>🔬 Lesson 2: Core Concepts</h1>

<p>Building on what we learned in <a href="lesson-1_TEMPLATE.html">Lesson 1</a>, let's explore some core concepts.</p>

<h2>🎓 Key Topics</h2>
<ol>
    <li><strong>Topic 1:</strong> Introduction to fundamental principles</li>
    <li><strong>Topic 2:</strong> Building on the basics</li>
    <li><strong>Topic 3:</strong> Advanced applications</li>
</ol>

<h2>📖 Additional Resources</h2>
<p>Review the <a href="../web_resources/resources_TEMPLATE.txt">additional resources</a> for supplementary information.</p>

<h2>✅ Knowledge Check</h2>
<p>After reviewing this lesson, test your understanding with the comprehensive quiz. The quiz includes examples of all question types available in Canvas.</p>

<h2>🔗 Navigation</h2>
<p>
    ← <a href="lesson-1_TEMPLATE.html">Back to Lesson 1</a> |
    <a href="welcome_TEMPLATE.html">Return to Home</a>
</p>

<div style="background-color: #e8f5e9; padding: 15px; margin-top: 20px; border-left: 4px solid #4CAF50;">
    <strong>✨ Template Features:</strong>
    <ul>
        <li>All links work locally for easy previewing</li>
        <li>Files are tagged with <code>_TEMPLATE</code> for easy removal</li>
        <li>Demonstrates various content formatting options</li>
    </ul>
</div>

</body>
</html>
"""

EXAMPLE_SYLLABUS = """Course Syllabus
===============

Course: Example Course
Code: COURSE101
Instructor: Your Name

Course Description:
This is an example course created with the IMSCC template system.

Week 1: Introduction and Getting Started
Week 2: Core Concepts
Week 3: Advanced Topics
Week 4: Final Project

Grading:
- Participation: 20%
- Assignments: 40%
- Quizzes: 20%
- Final Project: 20%

Contact:
Email: instructor@example.com
Office Hours: By appointment
"""

EXAMPLE_WEEK1_READING = """Week 1 Reading Material
======================

Introduction to the Course

This week we'll cover the fundamentals and set up our foundation
for the rest of the course.

Key Concepts:
1. Understanding the basics
2. Setting up your environment
3. First steps

Assignment:
- Read this material
- Complete the introduction quiz
- Post in the discussion forum
"""

EXAMPLE_RESOURCES = """Additional Course Resources
===========================

Recommended Reading:
- Book 1: Introduction to the Subject
- Book 2: Advanced Techniques
- Book 3: Best Practices

Online Resources:
- Course website
- Discussion forums
- Video tutorials

Support:
- Email: instructor@example.com
- Office hours available
- Peer discussion forum
"""

EXAMPLE_QUIZ_JSON = {
    "title": "Comprehensive Quiz - All Question Types",
    "description": "<p>This example quiz demonstrates all 12 available question types in Canvas.</p>",
    "settings": {
        "quiz_type": "assignment",
        "allowed_attempts": 2,
        "time_limit": 30,
        "shuffle_questions": True,
        "shuffle_answers": True,
        "show_correct_answers": True,
        "show_correct_answers_at": None,
        "one_question_at_a_time": False,
        "cant_go_back": False,
        "scoring_policy": "keep_highest"
    },
    "questions": [
        {
            "type": "multiple_choice",
            "text": "<p><strong>Multiple Choice:</strong> What is the capital of France?</p>",
            "answers": [
                {"text": "London", "correct": False},
                {"text": "Paris", "correct": True},
                {"text": "Berlin", "correct": False},
                {"text": "Madrid", "correct": False}
            ],
            "points": 1.0
        },
        {
            "type": "true_false",
            "text": "<p><strong>True/False:</strong> The Earth is flat.</p>",
            "correct_answer": False,
            "points": 1.0
        },
        {
            "type": "fill_in_blank",
            "text": "<p><strong>Fill in the Blank:</strong> The chemical symbol for water is ___.</p>",
            "answers": ["H2O", "h2o"],
            "points": 1.0
        },
        {
            "type": "fill_in_multiple_blanks",
            "text": "<p><strong>Fill in Multiple Blanks:</strong> The [color1] sky and the [color2] grass.</p>",
            "answers": {
                "color1": ["blue"],
                "color2": ["green"]
            },
            "points": 2.0
        },
        {
            "type": "multiple_answers",
            "text": "<p><strong>Multiple Answers:</strong> Which of the following are programming languages? (Select all that apply)</p>",
            "answers": [
                {"text": "Python", "correct": True},
                {"text": "JavaScript", "correct": True},
                {"text": "HTML", "correct": False},
                {"text": "Java", "correct": True}
            ],
            "points": 2.0
        },
        {
            "type": "multiple_dropdowns",
            "text": "<p><strong>Multiple Dropdowns:</strong> A [animal1] is a mammal, while a [animal2] is a reptile.</p>",
            "answers": {
                "animal1": [
                    {"text": "dog", "correct": True},
                    {"text": "snake", "correct": False},
                    {"text": "lizard", "correct": False}
                ],
                "animal2": [
                    {"text": "cat", "correct": False},
                    {"text": "snake", "correct": True},
                    {"text": "horse", "correct": False}
                ]
            },
            "points": 2.0
        },
        {
            "type": "matching",
            "text": "<p><strong>Matching:</strong> Match each country with its capital city.</p>",
            "matches": [
                {"prompt": "France", "answer": "Paris"},
                {"prompt": "Germany", "answer": "Berlin"},
                {"prompt": "Spain", "answer": "Madrid"},
                {"prompt": "Italy", "answer": "Rome"}
            ],
            "distractors": ["London", "Vienna"],
            "points": 2.0
        },
        {
            "type": "numerical_answer",
            "text": "<p><strong>Numerical Answer:</strong> What is the value of π (pi) to 2 decimal places?</p>",
            "answers": [
                {"exact": 3.14, "margin": 0.01}
            ],
            "points": 1.0
        },
        {
            "type": "formula_question",
            "text": "<p><strong>Formula Question:</strong> Calculate the area of a rectangle with length [l] and width [w].</p>",
            "formula": "l*w",
            "variables": {
                "l": [5, 20],
                "w": [3, 15]
            },
            "tolerance": 0.01,
            "points": 2.0
        },
        {
            "type": "essay_question",
            "text": "<p><strong>Essay Question:</strong> Describe the water cycle in 3-5 sentences.</p>",
            "points": 5.0
        },
        {
            "type": "file_upload_question",
            "text": "<p><strong>File Upload:</strong> Upload your completed diagram of the solar system.</p>",
            "points": 5.0
        },
        {
            "type": "text_only_question",
            "text": "<p><strong>Instructions:</strong> The following section contains bonus questions. Read carefully before proceeding.</p>",
            "points": 0.0
        }
    ]
}

EXAMPLE_ASSIGNMENT_JSON = {
    "title": "Comprehensive Assignment Example",
    "description": "<p>This assignment demonstrates all available features including submission types, file restrictions, and rubric integration.</p><h3>Requirements:</h3><ul><li>Complete all parts of the assignment</li><li>Submit your work as a PDF document</li><li>Review the rubric before submitting</li><li>Ensure all files are properly formatted</li></ul>",
    "points_possible": 100,
    "submission_types": ["online_upload", "online_text_entry"],
    "allowed_extensions": [".pdf", ".doc", ".docx", ".txt"],
    "grading_type": "points",
    "assignment_group": "Assignments",
    "rubric": "comprehensive-rubric_TEMPLATE",
    "due_at": None,
    "lock_at": None,
    "unlock_at": None
}

EXAMPLE_RUBRIC_JSON = {
    "title": "Comprehensive Rubric with Rating Descriptions",
    "criteria": [
        {
            "description": "Content Quality",
            "long_description": "Depth, accuracy, and relevance of content provided",
            "points": 25,
            "ratings": [
                {
                    "description": "Exemplary",
                    "long_description": "Content is exceptionally thorough, highly accurate, and demonstrates deep understanding. All required elements are present and exceed expectations.",
                    "points": 25
                },
                {
                    "description": "Proficient",
                    "long_description": "Content is complete, accurate, and demonstrates solid understanding. All required elements are present and meet expectations.",
                    "points": 20
                },
                {
                    "description": "Developing",
                    "long_description": "Content is mostly complete but may have minor inaccuracies or gaps. Most required elements are present.",
                    "points": 15
                },
                {
                    "description": "Beginning",
                    "long_description": "Content has significant gaps or inaccuracies. Several required elements are missing or incomplete.",
                    "points": 10
                },
                {
                    "description": "Incomplete",
                    "long_description": "Content is minimal, largely inaccurate, or missing most required elements.",
                    "points": 0
                }
            ]
        },
        {
            "description": "Organization & Structure",
            "long_description": "Logical flow, clear structure, and effective organization of ideas",
            "points": 20,
            "ratings": [
                {
                    "description": "Exemplary",
                    "long_description": "Exceptionally well-organized with clear, logical flow. Ideas are presented in a coherent sequence that enhances understanding.",
                    "points": 20
                },
                {
                    "description": "Proficient",
                    "long_description": "Well-organized with good flow. Ideas follow a logical sequence and are easy to follow.",
                    "points": 16
                },
                {
                    "description": "Developing",
                    "long_description": "Generally organized but may have some unclear transitions or sequencing issues.",
                    "points": 12
                },
                {
                    "description": "Beginning",
                    "long_description": "Poorly organized with unclear structure. Ideas are difficult to follow.",
                    "points": 8
                },
                {
                    "description": "Incomplete",
                    "long_description": "No clear organization or structure evident.",
                    "points": 0
                }
            ]
        },
        {
            "description": "Analysis & Critical Thinking",
            "long_description": "Demonstration of analytical skills and critical evaluation",
            "points": 25,
            "ratings": [
                {
                    "description": "Exemplary",
                    "long_description": "Demonstrates exceptional analytical skills. Provides insightful connections, evaluates multiple perspectives, and draws well-supported conclusions.",
                    "points": 25
                },
                {
                    "description": "Proficient",
                    "long_description": "Demonstrates solid analytical skills. Makes relevant connections and draws appropriate conclusions supported by evidence.",
                    "points": 20
                },
                {
                    "description": "Developing",
                    "long_description": "Demonstrates basic analytical skills. Some connections are made but analysis may be superficial or incomplete.",
                    "points": 15
                },
                {
                    "description": "Beginning",
                    "long_description": "Minimal analytical thinking evident. Analysis is superficial or lacks supporting evidence.",
                    "points": 10
                },
                {
                    "description": "Incomplete",
                    "long_description": "No analytical thinking or critical evaluation evident.",
                    "points": 0
                }
            ]
        },
        {
            "description": "Writing Quality",
            "long_description": "Grammar, spelling, punctuation, and overall writing mechanics",
            "points": 15,
            "ratings": [
                {
                    "description": "Exemplary",
                    "long_description": "Writing is clear, concise, and error-free. Excellent command of grammar, spelling, and punctuation.",
                    "points": 15
                },
                {
                    "description": "Proficient",
                    "long_description": "Writing is clear with minimal errors. Good command of grammar, spelling, and punctuation.",
                    "points": 12
                },
                {
                    "description": "Developing",
                    "long_description": "Writing is generally clear but contains some errors that may distract from meaning.",
                    "points": 9
                },
                {
                    "description": "Beginning",
                    "long_description": "Writing contains numerous errors that interfere with understanding.",
                    "points": 6
                },
                {
                    "description": "Incomplete",
                    "long_description": "Writing quality is very poor with pervasive errors.",
                    "points": 0
                }
            ]
        },
        {
            "description": "Use of Evidence & Citations",
            "long_description": "Appropriate use of sources and proper citation format",
            "points": 15,
            "ratings": [
                {
                    "description": "Exemplary",
                    "long_description": "Excellent use of relevant, credible sources. All citations are properly formatted and integrated smoothly into the text.",
                    "points": 15
                },
                {
                    "description": "Proficient",
                    "long_description": "Good use of relevant sources. Citations are generally proper with minor formatting issues.",
                    "points": 12
                },
                {
                    "description": "Developing",
                    "long_description": "Adequate use of sources but may lack variety or credibility. Some citation errors present.",
                    "points": 9
                },
                {
                    "description": "Beginning",
                    "long_description": "Minimal use of sources or frequent citation errors. Sources may lack credibility.",
                    "points": 6
                },
                {
                    "description": "Incomplete",
                    "long_description": "No sources cited or pervasive citation problems.",
                    "points": 0
                }
            ]
        }
    ]
}

DEFAULT_COURSE_JSON = {
    "title": "My Canvas Course",
    "course_code": "COURSE101",
    "default_view": "wiki",
    "description": "A course created from local templates"
}

DEFAULT_MODULES_JSON = {
    "modules": [
        {
            "title": "Getting Started",
            "items": [
                {"type": "page", "id": "welcome_TEMPLATE"},
                {"type": "page", "id": "lesson-1_TEMPLATE"},
                {"type": "assignment", "id": "comprehensive-assignment_TEMPLATE"}
            ]
        },
        {
            "title": "Example Content",
            "items": [
                {"type": "page", "id": "lesson-2_TEMPLATE"},
                {"type": "quiz", "id": "comprehensive-quiz_TEMPLATE"}
            ]
        }
    ]
}


def create_template(output_dir):
    """Create a template folder structure."""
    output_path = Path(output_dir)
    
    if output_path.exists():
        print(f"❌ Error: Directory '{output_dir}' already exists!")
        print(f"   Please choose a different name or remove the existing directory.")
        return False
    
    print("\n" + "=" * 70)
    print(f"Creating Course Template: {output_dir}")
    print("=" * 70)
    
    # Create directory structure
    print("\n📁 Creating folder structure...")
    wiki_dir = output_path / "wiki_content"
    files_dir = output_path / "web_resources"
    quizzes_dir = output_path / "quizzes"
    assignments_dir = output_path / "assignments"
    rubrics_dir = output_path / "rubrics"
    
    wiki_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)
    quizzes_dir.mkdir(parents=True)
    assignments_dir.mkdir(parents=True)
    rubrics_dir.mkdir(parents=True)
    print(f"   ✓ {wiki_dir}")
    print(f"   ✓ {files_dir}")
    print(f"   ✓ {quizzes_dir}")
    print(f"   ✓ {assignments_dir}")
    print(f"   ✓ {rubrics_dir}")
    
    # Create example pages
    print("\n📝 Creating example pages...")
    pages = {
        "welcome_TEMPLATE.html": EXAMPLE_PAGE_WITH_FILE_LINK,
        "lesson-1_TEMPLATE.html": EXAMPLE_LESSON_PAGE,
        "lesson-2_TEMPLATE.html": EXAMPLE_LESSON_2_PAGE,
    }
    
    for filename, content in pages.items():
        filepath = wiki_dir / filename
        filepath.write_text(content, encoding='utf-8')
        print(f"   ✓ wiki_content/{filename}")
    
    # Create example files
    print("\n📄 Creating example files...")
    files = {
        "syllabus_TEMPLATE.txt": EXAMPLE_SYLLABUS,
        "week1-reading_TEMPLATE.txt": EXAMPLE_WEEK1_READING,
        "resources_TEMPLATE.txt": EXAMPLE_RESOURCES,
    }
    
    for filename, content in files.items():
        filepath = files_dir / filename
        filepath.write_text(content, encoding='utf-8')
        print(f"   ✓ web_resources/{filename}")
    
    # Create example quiz
    print("\n📝 Creating example quiz...")
    quiz_path = quizzes_dir / "comprehensive-quiz_TEMPLATE.json"
    quiz_path.write_text(json.dumps(EXAMPLE_QUIZ_JSON, indent=2), encoding='utf-8')
    print(f"   ✓ quizzes/comprehensive-quiz_TEMPLATE.json")
    
    # Create example assignment
    print("\n📋 Creating example assignment...")
    assignment_path = assignments_dir / "comprehensive-assignment_TEMPLATE.json"
    assignment_path.write_text(json.dumps(EXAMPLE_ASSIGNMENT_JSON, indent=2), encoding='utf-8')
    print(f"   ✓ assignments/comprehensive-assignment_TEMPLATE.json")
    
    # Create example rubric
    print("\n📊 Creating example rubric...")
    rubric_path = rubrics_dir / "comprehensive-rubric_TEMPLATE.json"
    rubric_path.write_text(json.dumps(EXAMPLE_RUBRIC_JSON, indent=2), encoding='utf-8')
    print(f"   ✓ rubrics/comprehensive-rubric_TEMPLATE.json")
    
    # Create course.json
    print("\n⚙️  Creating configuration files...")
    course_json_path = output_path / "course.json"
    course_json_path.write_text(json.dumps(DEFAULT_COURSE_JSON, indent=2), encoding='utf-8')
    print(f"   ✓ course.json")
    
    # Create modules.json
    modules_json_path = output_path / "modules.json"
    modules_json_path.write_text(json.dumps(DEFAULT_MODULES_JSON, indent=2), encoding='utf-8')
    print(f"   ✓ modules.json")
    
    # Create README
    print("\n📖 Creating README...")
    readme_content = f"""# {DEFAULT_COURSE_JSON['title']}

This is a **comprehensive Canvas course template** created with the IMSCC tools, demonstrating all available features.

## 🎯 Template Files

All example files are tagged with `_TEMPLATE` in their filenames for easy identification and removal:

- **Pages:** `welcome_TEMPLATE.html`, `lesson-1_TEMPLATE.html`, `lesson-2_TEMPLATE.html`
- **Files:** `syllabus_TEMPLATE.txt`, `week1-reading_TEMPLATE.txt`, `resources_TEMPLATE.txt`
- **Quiz:** `comprehensive-quiz_TEMPLATE.json` (demonstrates all 12 question types)
- **Assignment:** `comprehensive-assignment_TEMPLATE.json` (with rubric integration)
- **Rubric:** `comprehensive-rubric_TEMPLATE.json` (5 criteria with detailed rating descriptions)

**To remove templates:** Delete all files containing `_TEMPLATE` when you're ready to add your own content.

## 📁 Folder Structure

```
{output_dir}/
├── wiki_content/                            # HTML pages for your course
│   ├── welcome_TEMPLATE.html                # Home page example
│   ├── lesson-1_TEMPLATE.html               # Lesson page with file links
│   └── lesson-2_TEMPLATE.html               # Lesson page with navigation
├── web_resources/                           # Files (PDFs, images, documents)
│   ├── syllabus_TEMPLATE.txt                # Example syllabus
│   ├── week1-reading_TEMPLATE.txt           # Example reading material
│   └── resources_TEMPLATE.txt               # Example resources
├── quizzes/                                 # Quiz definitions (JSON)
│   └── comprehensive-quiz_TEMPLATE.json     # All 12 question types!
├── assignments/                             # Assignment definitions (JSON)
│   └── comprehensive-assignment_TEMPLATE.json
├── rubrics/                                 # Rubrics (JSON format)
│   └── comprehensive-rubric_TEMPLATE.json   # 5 criteria, 5 ratings each
├── course.json                              # Course metadata
├── modules.json                             # Module organization
└── README.md                                # This file
```

## 🚀 Working Locally

1. **Edit pages**: Open HTML files in `wiki_content/` with your favorite editor
2. **Preview**: Open HTML files directly in your browser - all links work locally!
3. **Add files**: Place PDFs, images, etc. in `web_resources/`
4. **Create content**: Add quizzes, assignments, and rubrics as JSON files
5. **Organize**: Update `modules.json` to organize all content into modules

## 📄 Page Metadata

Each page can have metadata in HTML comments at the top:

```html
<!-- CANVAS_META
title: My Page Title
home: true
-->
```

Supported metadata:
- `title`: Page title (defaults to filename)
- `home`: Set to `true` to make this the course home page

## 🔗 Linking

### Link to files:
```html
<a href="../web_resources/syllabus.txt">Syllabus</a>
```

### Link to other pages:
```html
<a href="lesson-1.html">Go to Lesson 1</a>
```

These links work locally for preview. When you export to IMSCC, they're automatically
converted to Canvas format.

## Export to IMSCC

When ready to upload to Canvas:

```bash
python3 build_from_template.py {output_dir}
```

This will create `{DEFAULT_COURSE_JSON['course_code']}.imscc` that you can import into Canvas.

## 📊 Quizzes

Create quiz files in `quizzes/` using JSON format. The template includes a comprehensive example with **all 12 question types**:

### Question Types Supported:
1. **`multiple_choice`** - One correct answer from multiple options
2. **`true_false`** - Simple true or false question
3. **`fill_in_blank`** - Short text answer (exact match)
4. **`fill_in_multiple_blanks`** - Multiple blanks with different answers
5. **`multiple_answers`** - Select all correct answers (checkboxes)
6. **`multiple_dropdowns`** - Multiple dropdown menus in text
7. **`matching`** - Match items between two columns
8. **`numerical_answer`** - Numeric answer with tolerance/range
9. **`formula_question`** - Calculated question with variables
10. **`essay_question`** - Long-form text response (manual grading)
11. **`file_upload_question`** - File submission (manual grading)
12. **`text_only_question`** - Informational text (0 points)

See `comprehensive-quiz_TEMPLATE.json` for examples of each type!

### Quiz Settings:
```json
{{
  "title": "My Quiz",
  "description": "<p>Quiz description</p>",
  "settings": {{
    "quiz_type": "assignment",
    "allowed_attempts": 2,
    "time_limit": 30,
    "shuffle_questions": true,
    "shuffle_answers": true,
    "show_correct_answers": true,
    "one_question_at_a_time": false,
    "cant_go_back": false,
    "scoring_policy": "keep_highest"
  }},
  "questions": [...]
}}
```

## 📋 Assignments

Create assignment files in `assignments/` using JSON format:

```json
{{
  "title": "Assignment Title",
  "description": "<p>Assignment instructions</p>",
  "points_possible": 100,
  "submission_types": ["online_upload", "online_text_entry"],
  "allowed_extensions": [".pdf", ".doc", ".docx"],
  "grading_type": "points",
  "assignment_group": "Assignments",
  "rubric": "rubric-filename"
}}
```

**Submission Types:** `online_upload`, `online_text_entry`, `online_url`, `media_recording`

## 📏 Rubrics

Create rubrics in `rubrics/` as JSON files. The template includes a detailed example with 5 criteria and 5 rating levels each:

```json
{{
  "title": "Rubric Title",
  "criteria": [
    {{
      "description": "Criterion Name",
      "long_description": "Detailed description of what this criterion evaluates",
      "points": 25,
      "ratings": [
        {{
          "description": "Exemplary",
          "long_description": "Detailed description of exemplary performance",
          "points": 25
        }},
        {{
          "description": "Proficient",
          "long_description": "Detailed description of proficient performance",
          "points": 20
        }}
      ]
    }}
  ]
}}
```

**Note:** Both criteria and ratings support `long_description` for detailed feedback guidance.

## 📚 Module Organization

Edit `modules.json` to organize all content types into modules:

```json
{{
  "modules": [
    {{
      "title": "Week 1",
      "items": [
        {{"type": "page", "id": "welcome"}},
        {{"type": "page", "id": "lesson-1"}},
        {{"type": "quiz", "id": "week-1-quiz"}},
        {{"type": "assignment", "id": "homework-1"}}
      ]
    }}
  ]
}}
```

**Content Types:** `page`, `quiz`, `assignment`  
**IDs:** Match filenames without extensions (e.g., `welcome_TEMPLATE.html` → `"id": "welcome_TEMPLATE"`)

## 🔨 Export to IMSCC

When ready to upload to Canvas:

```bash
python3 build_from_template.py {output_dir}
```

This will create `{DEFAULT_COURSE_JSON['course_code']}.imscc` that you can import into Canvas.

## 💡 Tips

1. **Preview locally**: All links work in your browser before exporting
2. **Easy cleanup**: Delete all `_TEMPLATE` files when ready to add your content
3. **Reference examples**: Keep template files while learning the system
4. **Comprehensive examples**: Check the quiz file to see all 12 question types in action
5. **Rubric details**: Use `long_description` fields for clear grading criteria
"""
    
    readme_path = output_path / "README.md"
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"   ✓ README.md")
    
    # Success message
    print("\n" + "=" * 70)
    print("✅ Template Created Successfully!")
    print("=" * 70)
    print(f"\n📂 Location: {output_path.absolute()}")
    print("\n✨ What's Included:")
    print("   • 3 example pages (with working links)")
    print("   • 3 example files (syllabus, readings, resources)")
    print("   • 1 comprehensive quiz (ALL 12 question types!)")
    print("   • 1 assignment (with rubric integration)")
    print("   • 1 detailed rubric (5 criteria, 5 ratings each)")
    print("   • Configuration files (course.json, modules.json)")
    print("\n🏷️  All template files tagged with '_TEMPLATE' for easy removal")
    print("\n🚀 Next Steps:")
    print(f"   1. cd {output_dir}")
    print(f"   2. Open wiki_content/welcome_TEMPLATE.html in your browser")
    print(f"   3. Review the comprehensive examples")
    print(f"   4. Delete _TEMPLATE files and add your content")
    print(f"   5. Run: python3 ../build_from_template.py . ")
    print(f"   6. Import the generated IMSCC file into Canvas")
    print("\n💡 Tip: The quiz demonstrates all 12 question types - perfect reference!\n")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Create a comprehensive Canvas course template for local development',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 create_template.py my-course
  python3 create_template.py biology-101
  python3 create_template.py "Introduction to Python"

The template includes:
  - Example pages with working links (tagged with _TEMPLATE)
  - Example files (syllabus, readings, resources)
  - Comprehensive quiz with ALL 12 question types
  - Assignment with rubric integration
  - Detailed rubric with rating descriptions
  - Configuration files (course.json, modules.json)
  - Complete README with documentation
        """
    )
    
    parser.add_argument(
        'directory',
        help='Name of the directory to create'
    )
    
    args = parser.parse_args()
    
    create_template(args.directory)


if __name__ == '__main__':
    main()
