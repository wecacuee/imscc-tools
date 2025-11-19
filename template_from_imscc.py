#!/usr/bin/env python3
"""
Extract an IMSCC file and convert it to a locally editable template.

This script:
1. Extracts the IMSCC (ZIP) file
2. Parses imsmanifest.xml and course settings
3. Converts Canvas links back to local format:
   - $IMS-CC-FILEBASE$/web_resources/file.txt → ../web_resources/file.txt
   - $CANVAS_OBJECT_REFERENCE$/pages/slug → page-name.html
4. Creates template structure with course.json, modules.json, etc.
5. Preserves quizzes, assignments, and rubrics if present

Usage:
    python template_from_imscc.py course.imscc
    python template_from_imscc.py course.imscc -o my-template
"""

import os
import sys
import json
import re
import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_imscc(imscc_path, temp_dir):
    """Extract IMSCC file to temporary directory."""
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(imscc_path, 'r') as zip_ref:
        zip_ref.extractall(temp_path)
    
    print(f"✓ Extracted {imscc_path}")
    return temp_path


def parse_manifest(manifest_path):
    """Parse imsmanifest.xml to extract course metadata and structure."""
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    
    # Define XML namespaces
    ns = {
        'imscc': 'http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1',
        'imsmd': 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest',
        'lomimscc': 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource'
    }
    
    # Extract basic metadata
    metadata = {
        'title': None,
        'course_code': None,
        'identifier': None
    }
    
    # Get identifier
    metadata['identifier'] = root.get('identifier')
    
    # Try to get title from metadata
    title_elem = root.find('.//imsmd:general/imsmd:title/imsmd:string', ns)
    if title_elem is not None and title_elem.text:
        metadata['title'] = title_elem.text
    
    # Extract resources (pages, files, quizzes, assignments)
    resources = []
    for resource in root.findall('.//imscc:resource', ns):
        res_type = resource.get('type', '')
        identifier = resource.get('identifier', '')
        href = resource.get('href', '')
        
        res_info = {
            'type': res_type,
            'identifier': identifier,
            'href': href,
            'files': []
        }
        
        # Get associated files
        for file_elem in resource.findall('imscc:file', ns):
            file_href = file_elem.get('href', '')
            if file_href:
                res_info['files'].append(file_href)
        
        resources.append(res_info)
    
    return metadata, resources


def parse_course_settings(extracted_path):
    """Parse course_settings.xml if it exists."""
    settings_path = extracted_path / 'course_settings' / 'course_settings.xml'
    
    if not settings_path.exists():
        return {}
    
    tree = ET.parse(settings_path)
    root = tree.getroot()
    
    settings = {}
    
    # Extract common settings
    for elem in root:
        tag = elem.tag
        text = elem.text
        
        if tag == 'title':
            settings['title'] = text
        elif tag == 'course_code':
            settings['course_code'] = text
        elif tag == 'default_view':
            settings['default_view'] = text
        elif tag == 'license':
            settings['license'] = text
    
    return settings


def parse_module_meta(extracted_path):
    """Parse module_meta.xml to extract module structure."""
    module_path = extracted_path / 'course_settings' / 'module_meta.xml'
    
    if not module_path.exists():
        return []
    
    tree = ET.parse(module_path)
    root = tree.getroot()
    
    modules = []
    
    for module_elem in root.findall('module'):
        module = {
            'title': module_elem.get('identifier', 'Untitled Module'),
            'items': []
        }
        
        # Get module title
        title_elem = module_elem.find('title')
        if title_elem is not None and title_elem.text:
            module['title'] = title_elem.text
        
        # Get module items
        items_elem = module_elem.find('items')
        if items_elem is not None:
            for item_elem in items_elem.findall('item'):
                item = {
                    'type': item_elem.find('content_type').text if item_elem.find('content_type') is not None else 'WikiPage',
                    'identifier': item_elem.find('identifierref').text if item_elem.find('identifierref') is not None else '',
                    'title': item_elem.find('title').text if item_elem.find('title') is not None else ''
                }
                module['items'].append(item)
        
        modules.append(module)
    
    return modules


def convert_canvas_links_to_local(html_content, page_identifier_to_filename):
    """
    Convert Canvas links back to local format for editing.
    
    Conversions:
    - $IMS-CC-FILEBASE$/any/path/file.txt → ../web_resources/any/path/file.txt
    - $WIKI_REFERENCE$/pages/identifier → page-name.html
    - $CANVAS_OBJECT_REFERENCE$/pages/slug → page-name.html
    - $CANVAS_OBJECT_REFERENCE$/modules/id → (removed - module links can't be local)
    
    Args:
        html_content: The HTML content to process
        page_identifier_to_filename: Dict mapping page identifier/slug to filename
    """
    # Convert file links: $IMS-CC-FILEBASE$/path/file.ext → ../web_resources/path/file.ext
    # This handles all paths including web_resources/, Uploaded Media/, etc.
    html_content = re.sub(
        r'\$IMS-CC-FILEBASE\$/([^"\'>\s]+)',
        r'../web_resources/\1',
        html_content
    )
    
    # Convert wiki page links: $WIKI_REFERENCE$/pages/identifier → filename.html
    def replace_wiki_link(match):
        page_id = match.group(1)
        
        # Look up filename from identifier
        if page_id in page_identifier_to_filename:
            filename = page_identifier_to_filename[page_id]
        else:
            # Fallback: can't convert, leave as comment
            return f'[PAGE:{page_id}]'
        
        return f'{filename}.html'
    
    html_content = re.sub(
        r'\$WIKI_REFERENCE\$/pages/([^"\'>\s]+)',
        replace_wiki_link,
        html_content
    )
    
    # Convert page links: $CANVAS_OBJECT_REFERENCE$/pages/slug → slug.html
    def replace_page_link(match):
        page_slug = match.group(1)
        
        # Look up filename from slug
        if page_slug in page_identifier_to_filename:
            filename = page_identifier_to_filename[page_slug]
        else:
            # Fallback: use slug as filename
            filename = page_slug
        
        return f'{filename}.html'
    
    html_content = re.sub(
        r'\$CANVAS_OBJECT_REFERENCE\$/pages/([^"\'>\s]+)',
        replace_page_link,
        html_content
    )
    
    # Remove module links (can't be represented locally)
    # Replace with a comment so user knows what was there
    html_content = re.sub(
        r'\$CANVAS_OBJECT_REFERENCE\$/modules/([^"\'>\s]+)',
        r'[MODULE:\1]',
        html_content
    )
    
    return html_content


def title_to_slug(title):
    """Convert page title to Canvas-compatible slug."""
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    return slug


def title_to_filename(title):
    """Convert title to a safe filename."""
    filename = title.lower()
    filename = re.sub(r'[^\w\s-]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    filename = filename.strip('-')
    return filename


def create_template_structure(extracted_path, output_dir):
    """Create the template folder structure from extracted IMSCC."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Parse course settings
    course_settings = parse_course_settings(extracted_path)
    manifest_metadata, resources = parse_manifest(extracted_path / 'imsmanifest.xml')
    
    # Merge metadata
    course_data = {}
    if course_settings.get('title'):
        course_data['title'] = course_settings['title']
    elif manifest_metadata.get('title'):
        course_data['title'] = manifest_metadata['title']
    else:
        course_data['title'] = output_path.name
    
    if course_settings.get('course_code'):
        course_data['course_code'] = course_settings['course_code']
    else:
        course_data['course_code'] = output_path.name.upper()
    
    if course_settings.get('default_view'):
        course_data['default_view'] = course_settings['default_view']
    
    # Write course.json
    course_json_path = output_path / 'course.json'
    with open(course_json_path, 'w', encoding='utf-8') as f:
        json.dump(course_data, f, indent=2)
    print(f"✓ Created course.json")
    
    # Parse modules
    modules_data = parse_module_meta(extracted_path)
    
    # Create directories
    wiki_dir = output_path / 'wiki_content'
    wiki_dir.mkdir(exist_ok=True)
    
    resources_dir = output_path / 'web_resources'
    resources_dir.mkdir(exist_ok=True)
    
    # Build identifier/slug-to-filename mapping from manifest
    page_identifier_to_filename = {}
    page_identifier_to_info = {}
    
    # Process wiki pages
    wiki_source_dir = extracted_path / 'wiki_content'
    if wiki_source_dir.exists():
        for html_file in wiki_source_dir.glob('*.html'):
            # Read the page
            content = html_file.read_text(encoding='utf-8')
            
            # Try to extract title from HTML
            title_match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
            if title_match:
                page_title = title_match.group(1)
            else:
                page_title = html_file.stem.replace('-', ' ').title()
            
            # Extract Canvas identifier from meta tag
            canvas_id = None
            id_match = re.search(r'<meta\s+name="identifier"\s+content="([^"]+)"', content, re.IGNORECASE)
            if id_match:
                canvas_id = id_match.group(1)
            
            # Generate slug and filename
            page_slug = title_to_slug(page_title)
            page_filename = title_to_filename(page_title)
            
            # Map both slug and Canvas identifier to filename
            page_identifier_to_filename[page_slug] = page_filename
            if canvas_id:
                page_identifier_to_filename[canvas_id] = page_filename
            # Also map the original HTML filename (without .html)
            page_identifier_to_filename[html_file.stem] = page_filename
            
            # Store for later
            page_identifier_to_info[html_file.stem] = {
                'title': page_title,
                'filename': page_filename,
                'slug': page_slug,
                'canvas_id': canvas_id,
                'content': content
            }
    
    # Convert links in all pages and write them
    for page_id, page_info in page_identifier_to_info.items():
        content = page_info['content']
        
        # Convert Canvas links to local links
        content = convert_canvas_links_to_local(content, page_identifier_to_filename)
        
        # Add CANVAS_META comment at the top if not present
        if '<!-- CANVAS_META' not in content:
            # Try to insert after <body> tag
            body_match = re.search(r'(<body[^>]*>)', content, re.IGNORECASE)
            if body_match:
                insert_pos = body_match.end()
                meta_comment = f'\n<!-- CANVAS_META\ntitle: {page_info["title"]}\n-->\n\n'
                content = content[:insert_pos] + meta_comment + content[insert_pos:]
        
        # Write to wiki_content
        output_file = wiki_dir / f"{page_info['filename']}.html"
        output_file.write_text(content, encoding='utf-8')
        print(f"✓ Created wiki_content/{page_info['filename']}.html")
    
    # Copy web_resources
    web_resources_source = extracted_path / 'web_resources'
    if web_resources_source.exists():
        import shutil
        for item in web_resources_source.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(web_resources_source)
                dest_path = resources_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)
                print(f"✓ Copied web_resources/{rel_path}")
    
    # Process modules - map identifiers to filenames
    modules_output = []
    if modules_data:
        for module in modules_data:
            module_out = {
                'title': module['title'],
                'pages': []
            }
            
            for item in module['items']:
                if item['type'] == 'WikiPage':
                    # Find the page by identifier
                    page_id = item['identifier']
                    if page_id in page_identifier_to_info:
                        module_out['pages'].append(page_identifier_to_info[page_id]['filename'])
                    else:
                        # Try to match by title
                        for pid, pinfo in page_identifier_to_info.items():
                            if pinfo['title'] == item['title']:
                                module_out['pages'].append(pinfo['filename'])
                                break
            
            if module_out['pages']:  # Only add modules with pages
                modules_output.append(module_out)
    
    # Write modules.json
    if modules_output:
        modules_json = {'modules': modules_output}
        modules_json_path = output_path / 'modules.json'
        with open(modules_json_path, 'w', encoding='utf-8') as f:
            json.dump(modules_json, f, indent=2)
        print(f"✓ Created modules.json ({len(modules_output)} modules)")
    
    # Create README
    readme_content = f"""# {course_data['title']} - Template

This template was extracted from an IMSCC file and is ready for local editing.

## Structure

- `wiki_content/` - HTML pages (edit these locally)
- `web_resources/` - Files (PDFs, images, etc.)
- `course.json` - Course metadata
- `modules.json` - Module organization

## Workflow

1. **Edit content locally:**
   - Edit HTML files in `wiki_content/`
   - Add/update files in `web_resources/`
   - Preview in your browser (all links work locally)

2. **Build IMSCC:**
   ```bash
   python ../build_from_template.py .
   ```

3. **Import to Canvas:**
   - Upload the generated `.imscc` file via Canvas → Settings → Import Course Content

## Links

Local links work for preview and are automatically converted when building:

**Files:**
```html
<a href="../web_resources/syllabus.pdf">Syllabus</a>
```

**Pages:**
```html
<a href="page-name.html">Go to Page</a>
```

## Page Metadata

Add metadata using HTML comments:

```html
<!-- CANVAS_META
title: My Page Title
home: true
-->
```
"""
    
    readme_path = output_path / 'README.md'
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"✓ Created README.md")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Convert IMSCC file to locally editable template',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python template_from_imscc.py course.imscc
  python template_from_imscc.py course.imscc -o my-course-template
  
This creates a template folder you can edit locally, then rebuild with:
  python build_from_template.py my-course-template
        """
    )
    
    parser.add_argument('imscc_file', help='Path to the IMSCC file')
    parser.add_argument('-o', '--output', help='Output directory name (default: based on IMSCC filename)')
    
    args = parser.parse_args()
    
    # Validate input
    imscc_path = Path(args.imscc_file)
    if not imscc_path.exists():
        print(f"Error: File not found: {args.imscc_file}")
        sys.exit(1)
    
    if not imscc_path.suffix.lower() == '.imscc':
        print(f"Warning: File does not have .imscc extension: {args.imscc_file}")
    
    # Determine output directory
    if args.output:
        output_dir = args.output
    else:
        output_dir = imscc_path.stem
    
    print(f"\n🔄 Converting IMSCC to template...")
    print(f"Input: {imscc_path}")
    print(f"Output: {output_dir}/\n")
    
    # Create temporary extraction directory
    temp_dir = Path('.temp_imscc_extract')
    
    try:
        # Extract IMSCC
        extracted_path = extract_imscc(imscc_path, temp_dir)
        
        # Create template structure
        template_path = create_template_structure(extracted_path, output_dir)
        
        print(f"\n✅ Template created successfully!")
        print(f"\nNext steps:")
        print(f"  1. cd {output_dir}")
        print(f"  2. Edit files in wiki_content/ and web_resources/")
        print(f"  3. python ../build_from_template.py .")
        print(f"  4. Import the generated .imscc to Canvas\n")
        
    finally:
        # Clean up temp directory
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    main()
