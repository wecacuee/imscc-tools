"""Course class for creating IMSCC packages."""

import os
import zipfile
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from .wiki_page import WikiPage
from .module import Module
from .resource import FileResource, FileManager
from .utils import generate_identifier, ensure_dir


class Course:
    """Represents a Canvas course and handles IMSCC package creation."""
    
    def __init__(
        self,
        title: str,
        course_code: Optional[str] = None,
        identifier: Optional[str] = None,
        license: str = "private",
        default_view: str = "modules"
    ):
        """
        Create a new course.
        
        Args:
            title: Course title
            course_code: Course code (defaults to title if not provided)
            identifier: Unique identifier (auto-generated if not provided)
            license: License type (private, public, cc_by, etc.)
            default_view: Default course view (modules, wiki, etc.)
        """
        self.title = title
        self.course_code = course_code or title
        self.identifier = identifier or generate_identifier()
        self.license = license
        self.default_view = default_view
        
        self.pages: List[WikiPage] = []
        self.modules: List[Module] = []
        self.assignments: List['Assignment'] = []
        self.assignment_groups: List['AssignmentGroup'] = []
        self.rubrics: List['Rubric'] = []
        self.quizzes: List['Quiz'] = []
        self.file_manager = FileManager()
        self._default_assignment_group = None
    
    def add_page(
        self,
        title: str,
        content: str,
        workflow_state: str = "active"
    ) -> WikiPage:
        """
        Add a wiki page to the course.
        
        Args:
            title: Page title
            content: HTML content
            workflow_state: Workflow state
        
        Returns:
            The created WikiPage
        """
        page = WikiPage(title, content, workflow_state=workflow_state)
        self.pages.append(page)
        return page
    
    def add_page_from_file(self, filepath: str, title: Optional[str] = None) -> WikiPage:
        """
        Add a wiki page from an HTML file.
        
        Args:
            filepath: Path to HTML file
            title: Optional title (extracted from file if not provided)
        
        Returns:
            The created WikiPage
        """
        page = WikiPage.from_file(filepath, title)
        self.pages.append(page)
        return page
    
    def add_module(self, module: Module) -> "Course":
        """
        Add a module to the course.
        
        Args:
            module: Module instance
        
        Returns:
            Self for chaining
        """
        module.position = len(self.modules) + 1
        self.modules.append(module)
        return self
    
    def create_module(self, title: str, **kwargs) -> Module:
        """
        Create and add a module to the course.
        
        Args:
            title: Module title
            **kwargs: Additional module arguments
        
        Returns:
            The created Module
        """
        module = Module(title, **kwargs)
        self.add_module(module)
        return module
    
    def add_file(
        self,
        filepath: str,
        destination_path: Optional[str] = None
    ) -> FileResource:
        """
        Add a file to the course.
        
        Args:
            filepath: Path to the file
            destination_path: Optional destination path within IMSCC
        
        Returns:
            The created FileResource
        """
        return self.file_manager.add_file(filepath, destination_path)
    
    def add_directory(
        self,
        directory: str,
        destination_prefix: str = "web_resources"
    ) -> List[FileResource]:
        """
        Add all files from a directory.
        
        Args:
            directory: Directory path
            destination_prefix: Prefix for files in IMSCC
        
        Returns:
            List of created FileResources
        """
        return self.file_manager.add_directory(directory, destination_prefix)
    
    def create_assignment_group(self, title: str, position: int = None, 
                               group_weight: float = 0.0) -> 'AssignmentGroup':
        """Create and add an assignment group to the course.
        
        Args:
            title: The assignment group title
            position: Position in the gradebook (auto-calculated if None)
            group_weight: Weight for weighted grading (0.0 = unweighted)
            
        Returns:
            The created AssignmentGroup
        """
        from .assignment import AssignmentGroup
        
        if position is None:
            position = len(self.assignment_groups) + 1
        
        group = AssignmentGroup(title=title, position=position, group_weight=group_weight)
        self.assignment_groups.append(group)
        return group
    
    def get_or_create_default_assignment_group(self) -> 'AssignmentGroup':
        """Get the default assignment group, creating it if it doesn't exist.
        
        Returns:
            The default assignment group named \"Assignments\"
        """
        if self._default_assignment_group is None:
            self._default_assignment_group = self.create_assignment_group(
                title="Assignments",
                position=1
            )
        return self._default_assignment_group
    
    def add_assignment(self, assignment: 'Assignment', 
                      assignment_group: 'AssignmentGroup' = None) -> None:
        """Add an assignment to the course.
        
        Args:
            assignment: The Assignment to add
            assignment_group: The group to assign to (uses default if None)
        """
        if assignment_group is None:
            assignment_group = self.get_or_create_default_assignment_group()
        
        # Set the assignment group reference
        assignment.assignment_group_identifierref = assignment_group.identifier
        
        # Auto-add rubric if attached to assignment and not already in course
        if assignment.rubric and assignment.rubric not in self.rubrics:
            self.add_rubric(assignment.rubric)
        
        self.assignments.append(assignment)
    
    def add_rubric(self, rubric: 'Rubric') -> None:
        """Add a rubric to the course.
        
        Args:
            rubric: The Rubric to add
        """
        self.rubrics.append(rubric)
    
    def add_quiz(self, quiz: 'Quiz', assignment_group: 'AssignmentGroup' = None) -> None:
        """Add a quiz to the course.
        
        Args:
            quiz: The Quiz to add
            assignment_group: The group to assign to (uses default if None)
        """
        if assignment_group is None:
            assignment_group = self.get_or_create_default_assignment_group()
        
        # Set the assignment group reference
        quiz.assignment_group_identifierref = assignment_group.identifier
        
        self.quizzes.append(quiz)
    
    def _generate_manifest(self) -> str:
        """Generate the imsmanifest.xml content."""
        # Root manifest element - attribute order matters for Canvas!
        manifest = Element('manifest')
        # Set attributes in the same order as Canvas exports
        manifest.set('identifier', self.identifier)
        manifest.set('xmlns', 'http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1')
        manifest.set('xmlns:lom', 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource')
        manifest.set('xmlns:lomimscc', 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest')
        manifest.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        manifest.set('xsi:schemaLocation', 
                    'http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 '
                    'http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imscp_v1p2_v1p0.xsd '
                    'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource '
                    'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lomresource_v1p0.xsd '
                    'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest '
                    'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lommanifest_v1p0.xsd')
        
        # Metadata
        metadata = SubElement(manifest, 'metadata')
        SubElement(metadata, 'schema').text = 'IMS Common Cartridge'
        SubElement(metadata, 'schemaversion').text = '1.1.0'
        
        lom = SubElement(metadata, 'lomimscc:lom')
        general = SubElement(lom, 'lomimscc:general')
        title_elem = SubElement(general, 'lomimscc:title')
        SubElement(title_elem, 'lomimscc:string').text = self.title
        
        lifecycle = SubElement(lom, 'lomimscc:lifeCycle')
        contribute = SubElement(lifecycle, 'lomimscc:contribute')
        date_elem = SubElement(contribute, 'lomimscc:date')
        SubElement(date_elem, 'lomimscc:dateTime').text = datetime.now().strftime('%Y-%m-%d')
        
        rights = SubElement(lom, 'lomimscc:rights')
        copyright_elem = SubElement(rights, 'lomimscc:copyrightAndOtherRestrictions')
        SubElement(copyright_elem, 'lomimscc:value').text = 'yes'
        desc_elem = SubElement(rights, 'lomimscc:description')
        SubElement(desc_elem, 'lomimscc:string').text = 'Private (Copyrighted) - http://en.wikipedia.org/wiki/Copyright'
        
        # Organizations
        organizations = SubElement(manifest, 'organizations')
        organization = SubElement(organizations, 'organization')
        organization.set('identifier', 'org_1')
        organization.set('structure', 'rooted-hierarchy')
        
        learning_modules = SubElement(organization, 'item')
        learning_modules.set('identifier', 'LearningModules')
        
        # Add modules to organization
        for module in self.modules:
            module_item = SubElement(learning_modules, 'item')
            module_item.set('identifier', module.identifier)
            title_elem = SubElement(module_item, 'title')
            title_elem.text = module.title
            
            # Add module items
            for item in module.items:
                item_elem = SubElement(module_item, 'item')
                item_elem.set('identifier', item.identifier)
                item_elem.set('identifierref', item.identifierref)
                item_title = SubElement(item_elem, 'title')
                item_title.text = item.title
        
        # Resources
        resources = SubElement(manifest, 'resources')
        
        # Course settings resource
        settings_id = generate_identifier()
        settings_resource = SubElement(resources, 'resource')
        settings_resource.set('identifier', settings_id)
        settings_resource.set('type', 'associatedcontent/imscc_xmlv1p1/learning-application-resource')
        settings_resource.set('href', 'course_settings/canvas_export.txt')
        
        SubElement(settings_resource, 'file').set('href', 'course_settings/course_settings.xml')
        SubElement(settings_resource, 'file').set('href', 'course_settings/files_meta.xml')
        SubElement(settings_resource, 'file').set('href', 'course_settings/context.xml')
        SubElement(settings_resource, 'file').set('href', 'course_settings/media_tracks.xml')
        SubElement(settings_resource, 'file').set('href', 'course_settings/canvas_export.txt')
        
        if self.modules:
            SubElement(settings_resource, 'file').set('href', 'course_settings/module_meta.xml')
        
        if self.assignment_groups:
            SubElement(settings_resource, 'file').set('href', 'course_settings/assignment_groups.xml')
        
        if self.rubrics:
            SubElement(settings_resource, 'file').set('href', 'course_settings/rubrics.xml')
        
        # Wiki page resources
        for page in self.pages:
            resource = SubElement(resources, 'resource')
            resource.set('identifier', page.identifier)
            resource.set('type', 'webcontent')
            resource.set('href', f'wiki_content/{page.filename}')
            SubElement(resource, 'file').set('href', f'wiki_content/{page.filename}')
        
        # Assignment resources
        for assignment in self.assignments:
            resource = SubElement(resources, 'resource')
            resource.set('identifier', assignment.identifier)
            resource.set('type', 'associatedcontent/imscc_xmlv1p1/learning-application-resource')
            resource.set('href', f'{assignment.identifier}/assignment.html')
            SubElement(resource, 'file').set('href', f'{assignment.identifier}/assignment.html')
            SubElement(resource, 'file').set('href', f'{assignment.identifier}/assignment_settings.xml')
        
        # Quiz resources
        for quiz in self.quizzes:
            # Main quiz resource
            quiz_resource = SubElement(resources, 'resource')
            quiz_resource.set('identifier', quiz.identifier)
            quiz_resource.set('type', 'imsqti_xmlv1p2/imscc_xmlv1p1/assessment')
            SubElement(quiz_resource, 'file').set('href', f'{quiz.identifier}/assessment_qti.xml')
            
            # Dependency resource
            dep_id = generate_identifier('i')
            SubElement(quiz_resource, 'dependency', identifierref=dep_id)
            
            # Associated content resource
            dep_resource = SubElement(resources, 'resource')
            dep_resource.set('identifier', dep_id)
            dep_resource.set('type', 'associatedcontent/imscc_xmlv1p1/learning-application-resource')
            dep_resource.set('href', f'{quiz.identifier}/assessment_meta.xml')
            SubElement(dep_resource, 'file').set('href', f'{quiz.identifier}/assessment_meta.xml')
            SubElement(dep_resource, 'file').set('href', f'non_cc_assessments/{quiz.identifier}.xml.qti')
        
        # File resources
        for file_res in self.file_manager.files:
            resource = SubElement(resources, 'resource')
            resource.set('identifier', file_res.identifier)
            resource.set('type', 'webcontent')
            # Normalize path to use forward slashes for cross-platform compatibility
            normalized_path = file_res.destination_path.replace('\\', '/')
            resource.set('href', normalized_path)
            SubElement(resource, 'file').set('href', normalized_path)
        
        # Serialize to string without pretty printing first
        rough_string = tostring(manifest, encoding='utf-8')
        
        # Parse and pretty print, ensuring proper formatting
        dom = minidom.parseString(rough_string)
        
        # Custom serialization to match Canvas format
        xml_str = dom.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
        
        # Fix empty LearningModules item to use open/close tags instead of self-closing
        # Canvas expects <item identifier="LearningModules"></item> not <item ... />
        xml_str = xml_str.replace(
            '<item identifier="LearningModules"/>',
            '<item identifier="LearningModules">\n      </item>'
        )
        
        # Fix manifest tag attribute order to match Canvas exports exactly
        # Canvas puts identifier first, then xmlns attributes
        import re
        manifest_pattern = r'<manifest ([^>]+)>'
        manifest_match = re.search(manifest_pattern, xml_str)
        if manifest_match:
            # Rebuild manifest tag with correct attribute order
            manifest_tag = f'<manifest identifier="{self.identifier}" xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1" xmlns:lom="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource" xmlns:lomimscc="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imscp_v1p2_v1p0.xsd http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lomresource_v1p0.xsd http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lommanifest_v1p0.xsd">'
            xml_str = xml_str.replace(manifest_match.group(0), manifest_tag)
        
        return xml_str
    
    def _generate_course_settings(self) -> str:
        """Generate course_settings.xml content."""
        course = Element('course')
        course.set('identifier', self.identifier)
        course.set('xmlns', 'http://canvas.instructure.com/xsd/cccv1p0')
        course.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        course.set('xsi:schemaLocation', 
                  'http://canvas.instructure.com/xsd/cccv1p0 '
                  'https://canvas.instructure.com/xsd/cccv1p0.xsd')
        
        SubElement(course, 'title').text = self.title
        SubElement(course, 'course_code').text = self.course_code
        SubElement(course, 'start_at')
        SubElement(course, 'conclude_at')
        SubElement(course, 'is_public').text = 'false'
        SubElement(course, 'is_public_to_auth_users').text = 'false'
        SubElement(course, 'allow_student_wiki_edits').text = 'false'
        SubElement(course, 'allow_student_forum_attachments').text = 'false'
        SubElement(course, 'lock_all_announcements').text = 'false'
        SubElement(course, 'default_wiki_editing_roles').text = 'teachers'
        SubElement(course, 'allow_student_organized_groups').text = 'false'
        SubElement(course, 'default_view').text = self.default_view
        SubElement(course, 'open_enrollment').text = 'false'
        SubElement(course, 'filter_speed_grader_by_student_group').text = 'true'
        SubElement(course, 'self_enrollment').text = 'false'
        SubElement(course, 'license').text = self.license
        SubElement(course, 'indexed').text = 'false'
        SubElement(course, 'hide_final_grade').text = 'false'
        SubElement(course, 'hide_distribution_graphs').text = 'false'
        SubElement(course, 'allow_student_discussion_topics').text = 'false'
        SubElement(course, 'allow_student_discussion_editing').text = 'false'
        SubElement(course, 'show_announcements_on_home_page').text = 'false'
        SubElement(course, 'home_page_announcement_limit').text = '3'
        SubElement(course, 'usage_rights_required').text = 'false'
        SubElement(course, 'restrict_student_future_view').text = 'true'
        SubElement(course, 'restrict_student_past_view').text = 'false'
        SubElement(course, 'restrict_enrollments_to_course_dates').text = 'false'
        SubElement(course, 'homeroom_course').text = 'false'
        SubElement(course, 'horizon_course').text = 'false'
        SubElement(course, 'conditional_release').text = 'false'
        SubElement(course, 'content_library').text = 'false'
        SubElement(course, 'grading_standard_enabled').text = 'false'
        SubElement(course, 'storage_quota').text = '5000000000'
        SubElement(course, 'overridden_course_visibility')
        SubElement(course, 'root_account_uuid').text = generate_identifier('')  # Empty identifier for UUID
        
        default_post_policy = SubElement(course, 'default_post_policy')
        SubElement(default_post_policy, 'post_manually').text = 'false'
        
        SubElement(course, 'enable_course_paces').text = 'false'
        
        rough_string = tostring(course, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        xml_str = reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
        
        # Fix course tag attribute order to match Canvas (identifier first)
        import re
        course_pattern = r'<course ([^>]+)>'
        course_match = re.search(course_pattern, xml_str)
        if course_match:
            course_tag = f'<course identifier="{self.identifier}" xmlns="http://canvas.instructure.com/xsd/cccv1p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd">'
            xml_str = xml_str.replace(course_match.group(0), course_tag)
        
        return xml_str
    
    def _generate_module_meta(self) -> str:
        """Generate module_meta.xml content."""
        modules_elem = Element('modules')
        modules_elem.set('xmlns', 'http://canvas.instructure.com/xsd/cccv1p0')
        modules_elem.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        modules_elem.set('xsi:schemaLocation',
                        'http://canvas.instructure.com/xsd/cccv1p0 '
                        'https://canvas.instructure.com/xsd/cccv1p0.xsd')
        
        for module in self.modules:
            module_elem = SubElement(modules_elem, 'module')
            module_elem.set('identifier', module.identifier)
            
            SubElement(module_elem, 'title').text = module.title
            SubElement(module_elem, 'workflow_state').text = module.workflow_state
            SubElement(module_elem, 'position').text = str(module.position)
            SubElement(module_elem, 'require_sequential_progress').text = str(module.require_sequential_progress).lower()
            SubElement(module_elem, 'locked').text = str(module.locked).lower()
            
            items_elem = SubElement(module_elem, 'items')
            
            for item in module.items:
                item_elem = SubElement(items_elem, 'item')
                item_elem.set('identifier', item.identifier)
                
                SubElement(item_elem, 'content_type').text = item.content_type
                SubElement(item_elem, 'workflow_state').text = item.workflow_state
                SubElement(item_elem, 'title').text = item.title
                SubElement(item_elem, 'identifierref').text = item.identifierref
                SubElement(item_elem, 'position').text = str(item.position)
                SubElement(item_elem, 'new_tab')
                SubElement(item_elem, 'indent').text = str(item.indent)
                SubElement(item_elem, 'link_settings_json').text = 'null'
        
        rough_string = tostring(modules_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
    
    def _generate_assignment_groups(self) -> str:
        """Generate assignment_groups.xml content."""
        groups_elem = Element('assignmentGroups')
        groups_elem.set('xmlns', 'http://canvas.instructure.com/xsd/cccv1p0')
        groups_elem.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        groups_elem.set('xsi:schemaLocation',
                       'http://canvas.instructure.com/xsd/cccv1p0 '
                       'https://canvas.instructure.com/xsd/cccv1p0.xsd')
        
        for group in self.assignment_groups:
            groups_elem.append(group.to_xml())
        
        rough_string = tostring(groups_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
    
    def _generate_rubrics(self) -> str:
        """Generate rubrics.xml content."""
        rubrics_elem = Element('rubrics')
        rubrics_elem.set('xmlns', 'http://canvas.instructure.com/xsd/cccv1p0')
        rubrics_elem.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        rubrics_elem.set('xsi:schemaLocation',
                        'http://canvas.instructure.com/xsd/cccv1p0 '
                        'https://canvas.instructure.com/xsd/cccv1p0.xsd')
        
        for rubric in self.rubrics:
            rubrics_elem.append(rubric.to_xml())
        
        rough_string = tostring(rubrics_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
    
    def export(self, output_path: str) -> None:
        """
        Export the course as an IMSCC file.
        
        Args:
            output_path: Path for the output .imscc file
        """
        # Create temporary directory for building the package
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory structure
            ensure_dir(os.path.join(temp_dir, 'course_settings'))
            ensure_dir(os.path.join(temp_dir, 'wiki_content'))
            ensure_dir(os.path.join(temp_dir, 'non_cc_assessments'))
            
            # Write manifest
            manifest_path = os.path.join(temp_dir, 'imsmanifest.xml')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(self._generate_manifest())
            
            # Write course settings
            settings_path = os.path.join(temp_dir, 'course_settings', 'course_settings.xml')
            with open(settings_path, 'w', encoding='utf-8') as f:
                f.write(self._generate_course_settings())
            
            # Write files_meta.xml with folder structure
            files_meta_path = os.path.join(temp_dir, 'course_settings', 'files_meta.xml')
            with open(files_meta_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<fileMeta xmlns="http://canvas.instructure.com/xsd/cccv1p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd">\n')
                
                # Extract unique folder paths from file resources
                folders = set()
                for file_res in self.file_manager.files:
                    # Get directory path from destination_path
                    dest_path = Path(file_res.destination_path)
                    if len(dest_path.parts) > 1:  # Has subdirectories
                        # Add all parent folders (excluding the file itself)
                        for i in range(1, len(dest_path.parts) - 1):
                            folder_path = '/'.join(dest_path.parts[1:i+1])
                            folders.add(folder_path)
                
                # Write folder definitions if any exist
                if folders:
                    f.write('  <folders>\n')
                    for folder in sorted(folders):
                        f.write(f'    <folder path="{folder}">\n')
                        f.write('      <hidden>false</hidden>\n')
                        f.write('    </folder>\n')
                    f.write('  </folders>\n')
                
                f.write('</fileMeta>\n')
            
            context_path = os.path.join(temp_dir, 'course_settings', 'context.xml')
            with open(context_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<context_info xmlns="http://canvas.instructure.com/xsd/cccv1p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd">\n')
                f.write(f'  <course_name>{self.title}</course_name>\n')
                f.write('</context_info>\n')
            
            media_tracks_path = os.path.join(temp_dir, 'course_settings', 'media_tracks.xml')
            with open(media_tracks_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<media_tracks xmlns="http://canvas.instructure.com/xsd/cccv1p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd"/>\n')
            
            canvas_export_path = os.path.join(temp_dir, 'course_settings', 'canvas_export.txt')
            with open(canvas_export_path, 'w', encoding='utf-8') as f:
                # Canvas includes a joke in this file
                f.write('Q: What did the canvas say to the students?\n')
                f.write('A: I\'ve got you covered!')
            
            # Create non_cc_assessments directory (even if empty)
            non_cc_dir = os.path.join(temp_dir, 'non_cc_assessments')
            ensure_dir(non_cc_dir)
            # Add .keep file so directory is included in ZIP
            with open(os.path.join(non_cc_dir, '.keep'), 'w') as f:
                f.write('')
            
            # Write module metadata if modules exist
            if self.modules:
                module_meta_path = os.path.join(temp_dir, 'course_settings', 'module_meta.xml')
                with open(module_meta_path, 'w', encoding='utf-8') as f:
                    f.write(self._generate_module_meta())
            
            # Write assignment groups if they exist
            if self.assignment_groups:
                assignment_groups_path = os.path.join(temp_dir, 'course_settings', 'assignment_groups.xml')
                with open(assignment_groups_path, 'w', encoding='utf-8') as f:
                    f.write(self._generate_assignment_groups())
            
            # Write rubrics if they exist
            if self.rubrics:
                rubrics_path = os.path.join(temp_dir, 'course_settings', 'rubrics.xml')
                with open(rubrics_path, 'w', encoding='utf-8') as f:
                    f.write(self._generate_rubrics())
            
            # Write assignments
            for assignment in self.assignments:
                # Create assignment directory
                assignment_dir = os.path.join(temp_dir, assignment.identifier)
                ensure_dir(assignment_dir)
                
                # Write assignment HTML
                html_path = os.path.join(assignment_dir, 'assignment.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(assignment.get_html_content())
                
                # Write assignment settings XML
                settings_path = os.path.join(assignment_dir, 'assignment_settings.xml')
                with open(settings_path, 'w', encoding='utf-8') as f:
                    f.write(assignment.to_xml())
            
            # Write quizzes
            for quiz in self.quizzes:
                # Create quiz directory
                quiz_dir = os.path.join(temp_dir, quiz.identifier)
                ensure_dir(quiz_dir)
                
                # Write assessment_meta.xml
                meta_path = os.path.join(quiz_dir, 'assessment_meta.xml')
                with open(meta_path, 'w', encoding='utf-8') as f:
                    f.write(quiz.to_assessment_meta_xml())
                
                # Write assessment_qti.xml (shell)
                qti_path = os.path.join(quiz_dir, 'assessment_qti.xml')
                with open(qti_path, 'w', encoding='utf-8') as f:
                    f.write(quiz.to_assessment_qti_xml())
                
                # Write full QTI XML to non_cc_assessments
                qti_full_path = os.path.join(temp_dir, 'non_cc_assessments', f'{quiz.identifier}.xml.qti')
                with open(qti_full_path, 'w', encoding='utf-8') as f:
                    f.write(quiz.to_qti_xml())
            
            # Write wiki pages
            for page in self.pages:
                page_path = os.path.join(temp_dir, 'wiki_content', page.filename)
                with open(page_path, 'w', encoding='utf-8') as f:
                    f.write(page.to_html())
            
            # Copy files
            self.file_manager.copy_all(temp_dir)
            
            # Create ZIP file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
        
        print(f"✓ IMSCC package created: {output_path}")
