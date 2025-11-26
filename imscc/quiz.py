"""Quiz classes for Canvas quizzes with QTI question support."""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from .utils import generate_identifier
import uuid



class QuizQuestion:
    """Base class for quiz questions."""
    
    def __init__(
        self,
        question_text: str,
        points_possible: float = 1.0,
        identifier: Optional[str] = None
    ):
        """
        Create a quiz question.
        
        Args:
            question_text: The question text (HTML supported)
            points_possible: Points for this question
            identifier: Unique identifier (auto-generated if not provided)
        """
        self.question_text = question_text
        self.points_possible = points_possible
        self.identifier = identifier or self._generate_question_id()
        self.question_type = "question"  # Override in subclasses
        
    def _generate_question_id(self) -> str:
        """Generate a unique question identifier."""
        return uuid.uuid4().hex
    
    def to_qti_item(self) -> Element:
        """Generate QTI item element. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement to_qti_item()")


class MultipleChoiceQuestion(QuizQuestion):
    """Multiple choice question with one correct answer."""
    
    def __init__(
        self,
        question_text: str,
        answers: List[Dict[str, Any]],
        points_possible: float = 1.0,
        identifier: Optional[str] = None
    ):
        """
        Create a multiple choice question.
        
        Args:
            question_text: The question text (HTML)
            answers: List of answer dicts with 'text' and 'correct' keys
                Example: [
                    {'text': 'Answer 1', 'correct': True},
                    {'text': 'Answer 2', 'correct': False}
                ]
            points_possible: Points for this question
            identifier: Unique identifier
        """
        super().__init__(question_text, points_possible, identifier)
        self.answers = answers
        self.question_type = "multiple_choice_question"
        
        # Generate UUIDs for each answer
        for answer in self.answers:
            if 'id' not in answer:
                answer['id'] = str(uuid.uuid4())
    
    def to_qti_item(self) -> Element:
        """Generate QTI item XML for multiple choice question."""
        item = Element('item', ident=self.identifier, title=f"Question")
        
        # Item metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        # Question type
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'question_type'
        SubElement(field, 'fieldentry').text = self.question_type
        
        # Points possible
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'points_possible'
        SubElement(field, 'fieldentry').text = str(self.points_possible)
        
        # Original answer IDs
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'original_answer_ids'
        answer_ids = ','.join([a['id'] for a in self.answers])
        SubElement(field, 'fieldentry').text = answer_ids
        
        # Assessment question reference
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'assessment_question_identifierref'
        SubElement(field, 'fieldentry').text = self.identifier
        
        # Presentation (question text and answers)
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response choices
        response_lid = SubElement(presentation, 'response_lid', 
                                 ident='response1', rcardinality='Single')
        render_choice = SubElement(response_lid, 'render_choice')
        
        for answer in self.answers:
            response_label = SubElement(render_choice, 'response_label', 
                                       ident=answer['id'])
            ans_material = SubElement(response_label, 'material')
            ans_mattext = SubElement(ans_material, 'mattext', texttype='text/html')
            ans_mattext.text = answer['text']
        
        # Response processing (correct answer)
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # Find correct answer
        correct_answer = next((a for a in self.answers if a.get('correct')), None)
        if correct_answer:
            respcondition = SubElement(resprocessing, 'respcondition')
            respcondition.set('continue', 'No')
            conditionvar = SubElement(respcondition, 'conditionvar')
            varequal = SubElement(conditionvar, 'varequal', respident='response1')
            varequal.text = correct_answer['id']
            setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
            setvar.text = '100'
        
        return item


class TrueFalseQuestion(QuizQuestion):
    """True/False question."""
    
    def __init__(
        self,
        question_text: str,
        correct_answer: bool,
        points_possible: float = 1.0,
        identifier: Optional[str] = None
    ):
        """
        Create a true/false question.
        
        Args:
            question_text: The question text (HTML)
            correct_answer: True or False
            points_possible: Points for this question
            identifier: Unique identifier
        """
        super().__init__(question_text, points_possible, identifier)
        self.correct_answer = correct_answer
        self.question_type = "true_false_question"
        self.true_id = str(uuid.uuid4())
        self.false_id = str(uuid.uuid4())
    
    def to_qti_item(self) -> Element:
        """Generate QTI item XML for true/false question."""
        item = Element('item', ident=self.identifier, title="Question")
        
        # Item metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'question_type'
        SubElement(field, 'fieldentry').text = self.question_type
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'points_possible'
        SubElement(field, 'fieldentry').text = str(self.points_possible)
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'original_answer_ids'
        SubElement(field, 'fieldentry').text = f"{self.true_id},{self.false_id}"
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'assessment_question_identifierref'
        SubElement(field, 'fieldentry').text = self.identifier
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        response_lid = SubElement(presentation, 'response_lid', 
                                 ident='response1', rcardinality='Single')
        render_choice = SubElement(response_lid, 'render_choice')
        
        # True option
        true_label = SubElement(render_choice, 'response_label', ident=self.true_id)
        true_mat = SubElement(true_label, 'material')
        SubElement(true_mat, 'mattext', texttype='text/plain').text = 'True'
        
        # False option
        false_label = SubElement(render_choice, 'response_label', ident=self.false_id)
        false_mat = SubElement(false_label, 'material')
        SubElement(false_mat, 'mattext', texttype='text/plain').text = 'False'
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        respcondition = SubElement(resprocessing, 'respcondition')
        respcondition.set('continue', 'No')
        conditionvar = SubElement(respcondition, 'conditionvar')
        varequal = SubElement(conditionvar, 'varequal', respident='response1')
        varequal.text = self.true_id if self.correct_answer else self.false_id
        setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
        setvar.text = '100'
        
        return item


class FillInBlankQuestion(QuizQuestion):
    """Fill in the blank question - students enter short answer text."""
    
    def __init__(self, question_text: str, answers: List[str], points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.answers = answers  # List of acceptable answers
        self.question_type = 'fill_in_multiple_blanks_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('original_answer_ids', ','.join(str(i) for i in range(len(self.answers)))),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response section
        response_str = SubElement(presentation, 'response_str', ident='response1', rcardinality='Single')
        SubElement(response_str, 'render_fib')
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # Add condition for each acceptable answer
        for answer in self.answers:
            respcondition = SubElement(resprocessing, 'respcondition')
            respcondition.set('continue', 'No')
            conditionvar = SubElement(respcondition, 'conditionvar')
            varequal = SubElement(conditionvar, 'varequal', respident='response1')
            varequal.text = answer
            setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
            setvar.text = '100'
        
        return item


class FillInMultipleBlanksQuestion(QuizQuestion):
    """Fill in multiple blanks - students fill in multiple blanks in text."""
    
    def __init__(self, question_text: str, blanks: Dict[str, List[str]], points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.blanks = blanks  # Dict of {variable_name: [acceptable_answers]}
        self.question_type = 'fill_in_multiple_blanks_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response sections for each blank
        for var_name in self.blanks.keys():
            response_str = SubElement(presentation, 'response_str', 
                                     ident=var_name, rcardinality='Single')
            SubElement(response_str, 'render_fib')
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # Add conditions for each blank
        for var_name, answers in self.blanks.items():
            for answer in answers:
                respcondition = SubElement(resprocessing, 'respcondition')
                respcondition.set('continue', 'Yes')
                conditionvar = SubElement(respcondition, 'conditionvar')
                varequal = SubElement(conditionvar, 'varequal', respident=var_name)
                varequal.text = answer
                setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
                setvar.text = str(100 // len(self.blanks))
        
        return item


class MultipleAnswersQuestion(QuizQuestion):
    """Multiple answers question - students can select multiple correct answers."""
    
    def __init__(self, question_text: str, answers: List[Dict[str, Any]], points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.answers = answers  # List of dicts with 'text' and 'correct' keys
        self.question_type = 'multiple_answers_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        answer_ids = [str(i) for i in range(len(self.answers))]
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('original_answer_ids', ','.join(answer_ids)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response section - multiple cardinality
        response_lid = SubElement(presentation, 'response_lid', 
                                  ident='response1', rcardinality='Multiple')
        render_choice = SubElement(response_lid, 'render_choice')
        
        for i, answer in enumerate(self.answers):
            response_label = SubElement(render_choice, 'response_label', ident=str(i))
            material = SubElement(response_label, 'material')
            mattext = SubElement(material, 'mattext', texttype='text/plain')
            mattext.text = answer['text']
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # All correct answers must be selected
        correct_ids = [str(i) for i, ans in enumerate(self.answers) if ans.get('correct', False)]
        
        respcondition = SubElement(resprocessing, 'respcondition')
        respcondition.set('continue', 'No')
        conditionvar = SubElement(respcondition, 'conditionvar')
        and_condition = SubElement(conditionvar, 'and')
        
        for correct_id in correct_ids:
            varequal = SubElement(and_condition, 'varequal', respident='response1')
            varequal.text = correct_id
        
        setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
        setvar.text = '100'
        
        return item


class MultipleDropdownsQuestion(QuizQuestion):
    """Multiple dropdowns - students select from dropdowns embedded in text."""
    
    def __init__(self, question_text: str, dropdowns: Dict[str, List[Dict[str, Any]]], points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.dropdowns = dropdowns  # Dict of {variable_name: [{'text': str, 'correct': bool}]}
        self.question_type = 'multiple_dropdowns_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response sections for each dropdown
        for var_name, options in self.dropdowns.items():
            response_lid = SubElement(presentation, 'response_lid', 
                                     ident=f'response_{var_name}', rcardinality='Single')
            render_choice = SubElement(response_lid, 'render_choice')
            
            for i, option in enumerate(options):
                response_label = SubElement(render_choice, 'response_label', ident=f'{var_name}_{i}')
                material = SubElement(response_label, 'material')
                mattext = SubElement(material, 'mattext', texttype='text/plain')
                mattext.text = option['text']
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # Add conditions for each dropdown
        for var_name, options in self.dropdowns.items():
            correct_option = next((f'{var_name}_{i}' for i, opt in enumerate(options) 
                                 if opt.get('correct', False)), None)
            if correct_option:
                respcondition = SubElement(resprocessing, 'respcondition')
                respcondition.set('continue', 'Yes')
                conditionvar = SubElement(respcondition, 'conditionvar')
                varequal = SubElement(conditionvar, 'varequal', respident=f'response_{var_name}')
                varequal.text = correct_option
                setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
                setvar.text = str(100 // len(self.dropdowns))
        
        return item


class MatchingQuestion(QuizQuestion):
    """Matching question - students match items from two columns."""
    
    def __init__(self, question_text: str, matches: List[Dict[str, str]], 
                 distractors: List[str] = None, points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.matches = matches  # List of dicts with 'prompt' and 'answer' keys
        self.distractors = distractors or []  # Extra answers that don't match
        self.question_type = 'matching_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response group
        for i, match in enumerate(self.matches):
            response_grp = SubElement(presentation, 'response_grp', 
                                     ident=f'response_{i}', rcardinality='Single')
            render_choice = SubElement(response_grp, 'render_choice')
            
            # Add all possible answers (correct + distractors)
            all_answers = [m['answer'] for m in self.matches] + self.distractors
            for j, answer in enumerate(all_answers):
                response_label = SubElement(render_choice, 'response_label', ident=f'answer_{j}')
                material = SubElement(response_label, 'material')
                mattext = SubElement(material, 'mattext', texttype='text/plain')
                mattext.text = answer
            
            # Add the prompt
            material = SubElement(response_grp, 'material')
            mattext = SubElement(material, 'mattext', texttype='text/plain')
            mattext.text = match['prompt']
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # Add conditions for each match
        all_answers = [m['answer'] for m in self.matches] + self.distractors
        for i, match in enumerate(self.matches):
            correct_answer_idx = all_answers.index(match['answer'])
            respcondition = SubElement(resprocessing, 'respcondition')
            respcondition.set('continue', 'Yes')
            conditionvar = SubElement(respcondition, 'conditionvar')
            varequal = SubElement(conditionvar, 'varequal', respident=f'response_{i}')
            varequal.text = f'answer_{correct_answer_idx}'
            setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
            setvar.text = str(100 // len(self.matches))
        
        return item


class NumericalAnswerQuestion(QuizQuestion):
    """Numerical answer question - students enter a number within a range."""
    
    def __init__(self, question_text: str, exact_answer: Optional[float] = None,
                 answer_range: Optional[Tuple[float, float]] = None, 
                 margin: float = 0.0, points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.exact_answer = exact_answer
        self.answer_range = answer_range
        self.margin = margin
        self.question_type = 'numerical_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response section
        response_str = SubElement(presentation, 'response_str', ident='response1', rcardinality='Single')
        SubElement(response_str, 'render_fib', fibtype='Decimal')
        
        # Response processing
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        # Add condition based on exact or range
        respcondition = SubElement(resprocessing, 'respcondition')
        respcondition.set('continue', 'No')
        conditionvar = SubElement(respcondition, 'conditionvar')
        
        if self.exact_answer is not None:
            if self.margin > 0:
                and_condition = SubElement(conditionvar, 'and')
                vargte = SubElement(and_condition, 'vargte', respident='response1')
                vargte.text = str(self.exact_answer - self.margin)
                varlte = SubElement(and_condition, 'varlte', respident='response1')
                varlte.text = str(self.exact_answer + self.margin)
            else:
                varequal = SubElement(conditionvar, 'varequal', respident='response1')
                varequal.text = str(self.exact_answer)
        elif self.answer_range is not None:
            and_condition = SubElement(conditionvar, 'and')
            vargte = SubElement(and_condition, 'vargte', respident='response1')
            vargte.text = str(self.answer_range[0])
            varlte = SubElement(and_condition, 'varlte', respident='response1')
            varlte.text = str(self.answer_range[1])
        
        setvar = SubElement(respcondition, 'setvar', action='Set', varname='SCORE')
        setvar.text = '100'
        
        return item


class FormulaQuestion(QuizQuestion):
    """Formula question - answer is calculated from variables."""
    
    def __init__(self, question_text: str, formula: str, 
                 variables: Dict[str, Tuple[float, float]], 
                 tolerance: float = 0.01, points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.formula = formula
        self.variables = variables  # Dict of {var_name: (min, max)}
        self.tolerance = tolerance
        self.question_type = 'calculated_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Add formula and variable metadata
        qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(qtimetadatafield, 'fieldlabel').text = 'formula_question_formula'
        SubElement(qtimetadatafield, 'fieldentry').text = self.formula
        
        for var_name, (min_val, max_val) in self.variables.items():
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = f'formula_variable_{var_name}_min'
            SubElement(qtimetadatafield, 'fieldentry').text = str(min_val)
            
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = f'formula_variable_{var_name}_max'
            SubElement(qtimetadatafield, 'fieldentry').text = str(max_val)
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response section
        response_str = SubElement(presentation, 'response_str', ident='response1', rcardinality='Single')
        SubElement(response_str, 'render_fib', fibtype='Decimal')
        
        # Response processing (simplified - actual calculation done by Canvas)
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        return item


class EssayQuestion(QuizQuestion):
    """Essay question - students write long-form text answer."""
    
    def __init__(self, question_text: str, points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.question_type = 'essay_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response section - essay
        response_str = SubElement(presentation, 'response_str', ident='response1', rcardinality='Single')
        SubElement(response_str, 'render_fib', fibtype='String', rows='10', columns='80')
        
        # Response processing (no automatic grading for essays)
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        return item


class FileUploadQuestion(QuizQuestion):
    """File upload question - students upload a file as their answer."""
    
    def __init__(self, question_text: str, points_possible: float = 1.0, identifier: Optional[str] = None):
        super().__init__(question_text, points_possible, identifier)
        self.question_type = 'file_upload_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', str(self.points_possible)),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        # Response section - file upload
        response_str = SubElement(presentation, 'response_str', ident='response1', rcardinality='Single')
        SubElement(response_str, 'render_fib', fibtype='File')
        
        # Response processing (no automatic grading)
        resprocessing = SubElement(item, 'resprocessing')
        outcomes = SubElement(resprocessing, 'outcomes')
        SubElement(outcomes, 'decvar', maxvalue='100', minvalue='0', 
                  varname='SCORE', vartype='Decimal')
        
        return item


class TextOnlyQuestion(QuizQuestion):
    """Text-only question - displays information without requiring an answer."""
    
    def __init__(self, question_text: str, identifier: Optional[str] = None):
        super().__init__(question_text, 0.0, identifier)
        self.question_type = 'text_only_question'
        
    def to_qti_item(self) -> Element:
        item = Element('item', ident=self.identifier, title="Question")
        
        # Metadata
        itemmetadata = SubElement(item, 'itemmetadata')
        qtimetadata = SubElement(itemmetadata, 'qtimetadata')
        
        metadata_fields = [
            ('question_type', self.question_type),
            ('points_possible', '0.0'),
            ('assessment_question_identifierref', self._generate_question_id())
        ]
        
        for label, entry in metadata_fields:
            qtimetadatafield = SubElement(qtimetadata, 'qtimetadatafield')
            SubElement(qtimetadatafield, 'fieldlabel').text = label
            SubElement(qtimetadatafield, 'fieldentry').text = entry
        
        # Presentation - only displays text, no response needed
        presentation = SubElement(item, 'presentation')
        material = SubElement(presentation, 'material')
        mattext = SubElement(material, 'mattext', texttype='text/html')
        mattext.text = self.question_text
        
        return item


class Quiz:
    """Represents a Canvas quiz."""
    
    def __init__(
        self,
        title: str,
        description: str = "",
        quiz_type: str = "assignment",
        identifier: Optional[str] = None,
        points_possible: Optional[float] = None,
        allowed_attempts: int = 1,
        scoring_policy: str = "keep_highest",
        shuffle_questions: bool = False,
        shuffle_answers: bool = False,
        time_limit: Optional[int] = None,
        due_at: Optional[str] = None,
        unlock_at: Optional[str] = None,
        lock_at: Optional[str] = None,
        show_correct_answers: bool = False,
        one_question_at_a_time: bool = False,
        cant_go_back: bool = False,
        **kwargs
    ):
        """
        Create a new quiz.
        
        Args:
            title: Quiz title
            description: HTML description
            quiz_type: assignment, practice_quiz, graded_survey, survey
            identifier: Unique identifier (auto-generated if not provided)
            points_possible: Total points (auto-calculated from questions if None)
            allowed_attempts: Number of attempts allowed (-1 for unlimited)
            scoring_policy: keep_highest, keep_latest, keep_average
            shuffle_questions: Randomize question order
            shuffle_answers: Randomize answer order
            time_limit: Time limit in minutes (None for no limit)
            due_at: Due date (ISO format or datetime)
            unlock_at: Unlock date
            lock_at: Lock date
            show_correct_answers: Show correct answers after completion
            one_question_at_a_time: Show one question per page
            cant_go_back: Prevent going back to previous questions
            **kwargs: Additional Canvas quiz properties
        """
        self.title = title
        self.description = description
        self.quiz_type = quiz_type
        self.identifier = identifier or generate_identifier()
        self._points_possible = points_possible
        self.allowed_attempts = allowed_attempts
        self.scoring_policy = scoring_policy
        self.shuffle_questions = shuffle_questions
        self.shuffle_answers = shuffle_answers
        self.time_limit = time_limit
        self.due_at = self._format_date(due_at) if due_at else ""
        self.unlock_at = self._format_date(unlock_at) if unlock_at else ""
        self.lock_at = self._format_date(lock_at) if lock_at else ""
        self.show_correct_answers = show_correct_answers
        self.one_question_at_a_time = one_question_at_a_time
        self.cant_go_back = cant_go_back
        
        self.questions: List[QuizQuestion] = []
        self.assignment_group_identifierref: Optional[str] = None
        
        # Additional properties
        self.calculator_type = kwargs.get('calculator_type', 'none')
        self.hide_results = kwargs.get('hide_results', '')
        self.require_lockdown_browser = kwargs.get('require_lockdown_browser', False)
        self.anonymous_submissions = kwargs.get('anonymous_submissions', False)
        self.could_be_locked = kwargs.get('could_be_locked', False)
        self.workflow_state = kwargs.get('workflow_state', 'published')
        
    def _format_date(self, date: Any) -> str:
        """Convert date to ISO format string."""
        if isinstance(date, datetime):
            return date.isoformat()
        elif isinstance(date, str):
            return date
        return ""
    
    @property
    def points_possible(self) -> float:
        """Calculate total points from questions if not explicitly set."""
        if self._points_possible is not None:
            return self._points_possible
        return sum(q.points_possible for q in self.questions)
    
    def add_question(self, question: QuizQuestion) -> 'Quiz':
        """Add a question to the quiz.
        
        Args:
            question: QuizQuestion instance
            
        Returns:
            Self for method chaining
        """
        self.questions.append(question)
        return self
    
    def to_assessment_meta_xml(self) -> str:
        """Generate assessment_meta.xml content."""
        quiz_elem = Element('quiz')
        quiz_elem.set('xmlns', 'http://canvas.instructure.com/xsd/cccv1p0')
        quiz_elem.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        quiz_elem.set('xsi:schemaLocation', 'http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd')
        quiz_elem.set('identifier', self.identifier)
        
        SubElement(quiz_elem, 'title').text = self.title
        SubElement(quiz_elem, 'description').text = self.description
        SubElement(quiz_elem, 'due_at').text = self.due_at
        SubElement(quiz_elem, 'lock_at').text = self.lock_at
        SubElement(quiz_elem, 'unlock_at').text = self.unlock_at
        SubElement(quiz_elem, 'shuffle_questions').text = str(self.shuffle_questions).lower()
        SubElement(quiz_elem, 'shuffle_answers').text = str(self.shuffle_answers).lower()
        SubElement(quiz_elem, 'calculator_type').text = self.calculator_type
        SubElement(quiz_elem, 'scoring_policy').text = self.scoring_policy
        SubElement(quiz_elem, 'hide_results').text = self.hide_results
        SubElement(quiz_elem, 'quiz_type').text = self.quiz_type
        SubElement(quiz_elem, 'points_possible').text = str(self.points_possible)
        SubElement(quiz_elem, 'require_lockdown_browser').text = str(self.require_lockdown_browser).lower()
        SubElement(quiz_elem, 'require_lockdown_browser_for_results').text = 'false'
        SubElement(quiz_elem, 'require_lockdown_browser_monitor').text = 'false'
        SubElement(quiz_elem, 'lockdown_browser_monitor_data')
        SubElement(quiz_elem, 'show_correct_answers').text = str(self.show_correct_answers).lower()
        SubElement(quiz_elem, 'anonymous_submissions').text = str(self.anonymous_submissions).lower()
        SubElement(quiz_elem, 'could_be_locked').text = str(self.could_be_locked).lower()
        SubElement(quiz_elem, 'disable_timer_autosubmission').text = 'false'
        SubElement(quiz_elem, 'allowed_attempts').text = str(self.allowed_attempts)
        SubElement(quiz_elem, 'build_on_last_attempt').text = 'false'
        SubElement(quiz_elem, 'one_question_at_a_time').text = str(self.one_question_at_a_time).lower()
        SubElement(quiz_elem, 'cant_go_back').text = str(self.cant_go_back).lower()
        SubElement(quiz_elem, 'available').text = 'false'
        SubElement(quiz_elem, 'one_time_results').text = 'false'
        SubElement(quiz_elem, 'show_correct_answers_last_attempt').text = 'false'
        SubElement(quiz_elem, 'only_visible_to_overrides').text = 'false'
        SubElement(quiz_elem, 'module_locked').text = 'false'
        SubElement(quiz_elem, 'allow_clear_mc_selection')
        SubElement(quiz_elem, 'disable_document_access').text = 'false'
        SubElement(quiz_elem, 'result_view_restricted').text = 'false'
        
        # Embedded assignment
        assignment = SubElement(quiz_elem, 'assignment', identifier=generate_identifier())
        SubElement(assignment, 'title').text = self.title
        SubElement(assignment, 'due_at').text = self.due_at
        SubElement(assignment, 'lock_at').text = self.lock_at
        SubElement(assignment, 'unlock_at').text = self.unlock_at
        SubElement(assignment, 'module_locked').text = 'false'
        SubElement(assignment, 'workflow_state').text = self.workflow_state
        SubElement(assignment, 'assignment_overrides')
        SubElement(assignment, 'assignment_overrides')
        SubElement(assignment, 'quiz_identifierref').text = self.identifier
        SubElement(assignment, 'allowed_extensions')
        SubElement(assignment, 'has_group_category').text = 'false'
        SubElement(assignment, 'points_possible').text = str(self.points_possible)
        SubElement(assignment, 'grading_type').text = 'points'
        SubElement(assignment, 'all_day').text = 'false'
        SubElement(assignment, 'submission_types').text = 'online_quiz'
        SubElement(assignment, 'position').text = '1'
        SubElement(assignment, 'turnitin_enabled').text = 'false'
        SubElement(assignment, 'vericite_enabled').text = 'false'
        SubElement(assignment, 'peer_review_count').text = '0'
        SubElement(assignment, 'peer_reviews').text = 'false'
        SubElement(assignment, 'automatic_peer_reviews').text = 'false'
        SubElement(assignment, 'anonymous_peer_reviews').text = 'false'
        SubElement(assignment, 'grade_group_students_individually').text = 'false'
        SubElement(assignment, 'freeze_on_copy').text = 'false'
        SubElement(assignment, 'omit_from_final_grade').text = 'false'
        SubElement(assignment, 'intra_group_peer_reviews').text = 'false'
        SubElement(assignment, 'only_visible_to_overrides').text = 'false'
        SubElement(assignment, 'post_to_sis').text = 'false'
        SubElement(assignment, 'moderated_grading').text = 'false'
        SubElement(assignment, 'grader_count').text = '0'
        SubElement(assignment, 'grader_comments_visible_to_graders').text = 'true'
        SubElement(assignment, 'anonymous_grading').text = 'false'
        SubElement(assignment, 'graders_anonymous_to_graders').text = 'false'
        SubElement(assignment, 'grader_names_visible_to_final_grader').text = 'true'
        SubElement(assignment, 'anonymous_instructor_annotations').text = 'false'
        
        post_policy = SubElement(assignment, 'post_policy')
        SubElement(post_policy, 'post_manually').text = 'false'
        
        if self.assignment_group_identifierref:
            SubElement(assignment, 'assignment_group_identifierref').text = self.assignment_group_identifierref
        
        SubElement(assignment, 'assignment_overrides')
        
        rough_string = tostring(quiz_elem, encoding='UTF-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
    
    def to_assessment_qti_xml(self) -> str:
        """Generate assessment_qti.xml (QTI shell/reference file)."""
        root = Element('questestinterop')
        root.set('xmlns', 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('xsi:schemaLocation', 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_qtiasiv1p2p1_v1p0.xsd')
        
        assessment = SubElement(root, 'assessment', ident=self.identifier, title="Question")
        
        qtimetadata = SubElement(assessment, 'qtimetadata')
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'cc_profile'
        SubElement(field, 'fieldentry').text = 'cc.exam.v0p1'
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'qmd_assessmenttype'
        SubElement(field, 'fieldentry').text = 'Examination'
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'qmd_scoretype'
        SubElement(field, 'fieldentry').text = 'Percentage'
        
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'cc_maxattempts'
        SubElement(field, 'fieldentry').text = str(self.allowed_attempts)
        
        SubElement(assessment, 'section', ident='root_section')
        
        rough_string = tostring(root, encoding='UTF-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
    
    def to_qti_xml(self) -> str:
        """Generate full QTI XML with all questions."""
        root = Element('questestinterop')
        root.set('xmlns', 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('xsi:schemaLocation', 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/xsd/ims_qtiasiv1p2p1.xsd')
        
        assessment = SubElement(root, 'assessment', ident=self.identifier, title="Question")
        
        # Add metadata
        qtimetadata = SubElement(assessment, 'qtimetadata')
        field = SubElement(qtimetadata, 'qtimetadatafield')
        SubElement(field, 'fieldlabel').text = 'cc_maxattempts'
        SubElement(field, 'fieldentry').text = str(self.allowed_attempts)
        
        # Add section with questions
        section = SubElement(assessment, 'section', ident='root_section')
        
        for question in self.questions:
            section.append(question.to_qti_item())
        
        rough_string = tostring(root, encoding='UTF-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')
