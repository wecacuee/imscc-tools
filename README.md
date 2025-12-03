# IMSCC Tools

Create Canvas Common Cartridge (IMSCC) course packages using Python — programmatically or from local templates.

## Features

- ✅ Wiki Pages, Modules, Files & Resources
- ✅ Quizzes (12 question types), Assignments, Rubrics
- ✅ Assignment Groups with weights
- ✅ Auto-converts local links to Canvas format
- ✅ Local HTML preview before import
- 🎯 Zero dependencies — Pure Python 3.7+

## Installation

```bash
git clone https://github.com/jcjeffreys/imscc-tools.git
cd imscc-tools
pip install -e .  # Optional
```

---

## Three Workflows

### 1. Programmatic (Python)

```python
from imscc import Course

course = Course(title="My Course", course_code="CS101")
course.add_page(title="Welcome", content="<h1>Hello!</h1>")
course.export("course.imscc")
```

### 2. Template-Based (Local Editing)

```bash
# Create template structure
python create_template.py biology-101
cd biology-101

# Edit HTML files in wiki_content/, add files to web_resources/
# Preview: open wiki_content/welcome.html

# Build IMSCC
python build_from_template.py .

# Upload biology-101.imscc to Canvas
```

### 3. Extract from IMSCC (Reverse Engineering)

```bash
# Extract existing IMSCC to editable template
python template_from_imscc.py existing-course.imscc

# Creates existing-course/ folder with:
# - wiki_content/*.html (local preview links)
# - web_resources/ (organized files)
# - course.json (metadata)
# - modules.json (module structure)

# Edit locally, then rebuild
python build_from_template.py existing-course
```

---

## Programmatic Examples

### Basic Course

```python
from imscc import Course

course = Course(title="Programming 101", course_code="CS101")

# Add pages
course.add_page(
    title="Welcome",
    content="<h1>Welcome to CS101!</h1><p>Let's learn Python.</p>"
)

# Add modules
module = course.create_module("Week 1")
page = course.add_page(title="Lesson 1", content="<h2>Variables</h2>")
module.add_page(page)

# Export
course.export("cs101.imscc")
```

### Course with Quizzes

```python
from imscc import Course, Quiz
from imscc.quiz import MultipleChoiceQuestion, TrueFalseQuestion

course = Course(title="Python Course", course_code="PY101")

# Create quiz
quiz = Quiz(
    title="Week 1 Quiz",
    description="<p>Test your knowledge</p>",
    quiz_type="assignment",
    allowed_attempts=2,
    time_limit=20
)

# Add questions
quiz.add_question(MultipleChoiceQuestion(
    question_text="<p>What is 2 + 2?</p>",
    answers=[
        {"text": "3", "correct": False},
        {"text": "4", "correct": True},
        {"text": "5", "correct": False}
    ],
    points_possible=1.0
))

quiz.add_question(TrueFalseQuestion(
    question_text="<p>Python is compiled.</p>",
    correct_answer=False,
    points_possible=1.0
))

course.add_quiz(quiz)
course.export("python-course.imscc")
```

### Course with Assignments and Rubrics

```python
from imscc import Course, Assignment, Rubric

course = Course(title="Programming 101", course_code="CS101")

# Create assignment groups
homework = course.create_assignment_group("Homework", group_weight=40.0)
projects = course.create_assignment_group("Projects", group_weight=60.0)

# Create rubric
rubric = Rubric(title="Project Rubric")
rubric.add_criterion(
    description="Code Quality",
    points=50,
    ratings=[
        {"description": "Excellent", "points": 50, "long_description": "Clean, well-organized code"},
        {"description": "Good", "points": 40, "long_description": "Minor issues"},
        {"description": "Fair", "points": 25, "long_description": "Needs improvement"},
        {"description": "Poor", "points": 0, "long_description": "Poorly written"}
    ]
)
course.add_rubric(rubric)

# Create assignment with rubric
assignment = Assignment(
    title="Final Project",
    description="<p>Build a complete application.</p>",
    points_possible=100,
    submission_types="online_upload",
    rubric_identifierref=rubric.identifier
)
course.add_assignment(assignment, projects)

course.export("course-with-assignments.imscc")
```

---

## Template Workflow

### Create Template

```bash
python create_template.py biology-101
```

Creates:
```
biology-101/
├── wiki_content/          # HTML pages (edit locally)
│   ├── welcome.html
│   ├── lesson-1.html
│   └── lesson-2.html
├── web_resources/         # Files (PDFs, images)
│   ├── syllabus.txt
│   └── week1-reading.txt
├── quizzes/              # Quiz JSON files
│   └── week-1-quiz.json
├── assignments/          # Assignment JSON files
│   └── week-1-homework.json
├── rubrics/              # Rubric JSON files
│   └── homework-rubric.json
├── course.json           # Course metadata
├── modules.json          # Module organization
└── README.md
```

### Edit Content Locally

**Pages** - Edit HTML in `wiki_content/`:
```html
<!DOCTYPE html>
<html>
<body>
<!-- CANVAS_META
title: Welcome to Biology 101
home: true
-->

<h1>Welcome!</h1>
<p><a href="../web_resources/syllabus.pdf">Download Syllabus</a></p>
<p><a href="lesson-1.html">Start Lesson 1</a></p>

</body>
</html>
```

**Files** - Add PDFs, images to `web_resources/`

**Quizzes** - Create JSON in `quizzes/`:
```json
{
  "title": "Week 1 Quiz",
  "description": "<p>Test your knowledge</p>",
  "settings": {
    "quiz_type": "assignment",
    "allowed_attempts": 2,
    "time_limit": 20
  },
  "questions": [
    {
      "type": "multiple_choice",
      "text": "<p>What is 2 + 2?</p>",
      "answers": [
        {"text": "3", "correct": false},
        {"text": "4", "correct": true}
      ],
      "points": 1.0
    }
  ]
}
```

### Build IMSCC

```bash
cd biology-101
python ../build_from_template.py .
```

Output: `biology-101.imscc` ready for Canvas import

### Link Auto-Conversion

Local links work for preview, then convert automatically:

**Before (local preview):**
```html
<a href="../web_resources/syllabus.pdf">Syllabus</a>
<a href="lesson-1.html">Lesson 1</a>
```

**After (in IMSCC):**
```html
<a href="$IMS-CC-FILEBASE$/web_resources/syllabus.pdf">Syllabus</a>
<a href="$CANVAS_OBJECT_REFERENCE$/pages/lesson-1">Lesson 1</a>
```

**Assignment Links:**

To link to assignments from pages, use the Canvas format directly (no local conversion needed):

```html
<a href="$CANVAS_OBJECT_REFERENCE$/assignments/week-01-homework">Week 1 Homework</a>
```

**Important:** Use the assignment's JSON filename (without `.json`) as the identifier.

Example:
- Assignment file: `assignments/week-01-homework.json`
- Link identifier: `week-01-homework`

The assignment identifier is set automatically from the filename during build.

---

## Quiz Question Types

All 12 Canvas question types supported:

| Type | Description |
|------|-------------|
| `multiple_choice` | One correct answer |
| `true_false` | True or false |
| `fill_in_blank` | Short text answer |
| `fill_in_multiple_blanks` | Multiple blanks with `[var]` syntax |
| `multiple_answers` | Select all that apply |
| `multiple_dropdowns` | Dropdowns in text |
| `matching` | Match columns |
| `numerical_answer` | Number with tolerance/range |
| `formula_question` | Calculated with variables |
| `essay_question` | Long-form text (manual grading) |
| `file_upload_question` | File upload (manual grading) |
| `text_only_question` | Informational (0 points) |

### Examples

**Multiple Choice:**
```json
{
  "type": "multiple_choice",
  "text": "<p>What is the capital of France?</p>",
  "answers": [
    {"text": "Paris", "correct": true},
    {"text": "London", "correct": false}
  ],
  "points": 1.0
}
```

**Fill in Multiple Blanks:**
```json
{
  "type": "fill_in_multiple_blanks",
  "text": "<p>The primary colors are [c1], [c2], and [c3].</p>",
  "blanks": {
    "c1": ["red", "Red"],
    "c2": ["blue", "Blue"],
    "c3": ["yellow", "Yellow"]
  },
  "points": 3.0
}
```

**Matching:**
```json
{
  "type": "matching",
  "text": "<p>Match data structures:</p>",
  "matches": [
    {"prompt": "Stack", "answer": "LIFO"},
    {"prompt": "Queue", "answer": "FIFO"}
  ],
  "points": 2.0
}
```

**Formula (Calculated):**
```json
{
  "type": "formula_question",
  "text": "<p>Rectangle: length=[l]m, width=[w]m. Area?</p>",
  "formula": "[l] * [w]",
  "variables": {
    "l": [5.0, 15.0],
    "w": [3.0, 10.0]
  },
  "tolerance": 0.1,
  "points": 2.0
}
```

---

## API Reference

### Course

```python
course = Course(
    title="Course Title",
    course_code="CODE101",
    identifier=None,           # Auto-generated
    license="private",
    default_view="modules"
)

# Add content
page = course.add_page(title, content, workflow_state="active")
page = course.add_page_from_file(filepath, title=None)

# Modules
module = course.create_module(title, **kwargs)

# Files
course.add_file(filepath, destination_path=None)
course.add_directory(directory, destination_prefix="web_resources")

# Quizzes & Assignments
course.add_quiz(quiz)
course.add_assignment(assignment, assignment_group=None)
course.add_rubric(rubric)

# Export
course.export("output.imscc")
```

### WikiPage

```python
page = WikiPage(
    title="Page Title",
    content="<p>HTML content</p>",
    workflow_state="active",
    editing_roles="teachers"
)

page = WikiPage.from_file("path/to/file.html", title=None)
```

### Module

```python
module = Module(
    title="Module Title",
    workflow_state="active",
    require_sequential_progress=False
)

module.add_item(title, content_type, identifierref, indent=0)
module.add_page(page, indent=0)
```

### Quiz

```python
quiz = Quiz(
    title="Quiz Title",
    description="<p>Description</p>",
    quiz_type="assignment",
    allowed_attempts=1,
    time_limit=None,
    shuffle_questions=False
)

quiz.add_question(question_object)
```

### Assignment

```python
assignment = Assignment(
    title="Assignment Title",
    description="<p>Instructions</p>",
    points_possible=100,
    submission_types="online_upload",
    allowed_extensions="pdf,doc,docx",
    grading_type="points",
    rubric_identifierref=None
)
```

### Rubric

```python
rubric = Rubric(title="Rubric Title")

rubric.add_criterion(
    description="Criterion Name",
    points=50,
    long_description="Details",
    ratings=[
        {"description": "Excellent", "points": 50, "long_description": "..."},
        {"description": "Good", "points": 40, "long_description": "..."}
    ]
)
```

---

## File Structure

Templates use this structure:

```
course-name/
├── course.json           # Course metadata
├── modules.json          # Module organization
├── wiki_content/         # HTML pages
├── web_resources/        # Files (PDFs, images)
├── quizzes/             # Quiz JSON files
├── assignments/         # Assignment JSON files
└── rubrics/             # Rubric JSON files
```

IMSCC output structure:

```
course.imscc (ZIP)
├── imsmanifest.xml
├── course_settings/
│   ├── course_settings.xml
│   ├── module_meta.xml
│   └── assignment_settings.xml
├── wiki_content/
│   └── *.html
└── web_resources/
    └── files...
```
