"""WikiPage class for IMSCC package."""

from typing import Optional
from .utils import generate_identifier, sanitize_filename


class WikiPage:
    """Represents a Canvas wiki page."""
    
    def __init__(
        self,
        title: str,
        content: str,
        identifier: Optional[str] = None,
        workflow_state: str = "active",
        editing_roles: str = "teachers",
        is_front_page: bool = False,
        previous_head: str = ""
    ):
        """
        Create a new wiki page.
        
        Args:
            title: Page title
            content: HTML content of the page
            identifier: Unique identifier (auto-generated if not provided)
            workflow_state: Workflow state (active, unpublished, etc.)
            editing_roles: Who can edit (teachers, students, etc.)
            is_front_page: Whether this page is the course front page
        """
        self.title = title
        self.content = content
        self.identifier = identifier or generate_identifier()
        self.workflow_state = workflow_state
        self.editing_roles = editing_roles
        self.is_front_page = is_front_page
        self._filename = f"{sanitize_filename(title)}.html"
        self.previous_head = previous_head
    
    @property
    def filename(self) -> str:
        """Get the filename for this page."""
        return self._filename
    
    def to_html(self) -> str:
        """
        Generate the HTML file content for this page.
        
        Returns:
            Complete HTML content with metadata
        """
        previous_head = self.previous_head
        front_page_meta = '<meta name="front_page" content="true"/>\n' if self.is_front_page else ''
        return f"""<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>{self.title}</title>
<meta name="identifier" content="{self.identifier}"/>
<meta name="editing_roles" content="{self.editing_roles}"/>
<meta name="workflow_state" content="{self.workflow_state}"/>
{front_page_meta}
{previous_head}
</head>
<body>
{self.content}
</body>
</html>"""
    
    @classmethod
    def from_file(cls, filepath: str, title: Optional[str] = None) -> "WikiPage":
        """
        Create a WikiPage from an HTML file.
        
        Args:
            filepath: Path to the HTML file
            title: Page title (extracted from file if not provided)
        
        Returns:
            WikiPage instance
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to extract title from HTML if not provided
        if title is None:
            import re
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
            else:
                title = filepath.split('/')[-1].replace('.html', '').replace('-', ' ').title()
        
        # Extract just the body content if it's a full HTML document
        body_match = re.search(r'<body>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
        if body_match:
            content = body_match.group(1).strip()
        
        return cls(title=title, content=content)
