from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, Set, List, Union, NamedTuple

from data_to_paper.base_steps import LiteratureSearch
from data_to_paper.conversation.stage import Stage
from data_to_paper.latex import extract_latex_section_from_response
from data_to_paper.latex.tables import add_tables_to_paper_section, get_table_caption

from data_to_paper.researches_types.scientific_research.cast import ScientificAgent
from data_to_paper.researches_types.scientific_research.scientific_stage import ScientificStages, \
    SECTION_NAMES_TO_WRITING_STAGES
from data_to_paper.run_gpt_code.types import CodeAndOutput
from data_to_paper.utils.mutable import Mutable
from data_to_paper.utils.nice_list import NiceList
from data_to_paper.base_products import DataFileDescriptions, DataFileDescription, Products, \
    NameDescriptionStageGenerator
from data_to_paper.servers.crossref import CrossrefCitation
from data_to_paper.utils.types import ListBasedSet, MemoryDict
from data_to_paper.servers.types import Citation

CODE_STEPS_TO_STAGES_NAMES_AGENTS: Dict[str, Tuple[Stage, str, ScientificAgent]] = {
    'data_exploration': (ScientificStages.EXPLORATION, 'Data Exploration', ScientificAgent.DataExplorer),
    'data_preprocessing': (ScientificStages.PREPROCESSING, 'Data Preprocessing', ScientificAgent.DataPreprocessor),
    'data_analysis': (ScientificStages.CODE, 'Data Analysis', ScientificAgent.Debugger),
}


def get_code_stage(code_step: str) -> Stage:
    """
    Return the stage of the code step.
    """
    return CODE_STEPS_TO_STAGES_NAMES_AGENTS[code_step][0]


def get_code_name(code_step: str) -> str:
    """
    Return the name of the code step.
    """
    return CODE_STEPS_TO_STAGES_NAMES_AGENTS[code_step][1]


def get_code_agent(code_step: str) -> ScientificAgent:
    """
    Return the agent of the code step.
    """
    return CODE_STEPS_TO_STAGES_NAMES_AGENTS[code_step][2]


def convert_description_of_created_files_to_string(description_of_created_files: Dict[str, str]) -> Optional[str]:
    """
    Convert the description of created files to a string.
    """
    if not description_of_created_files:
        return None
    return '\n'.join(
        f'File "{file_name}":\n\n{file_description}'
        for file_name, file_description in description_of_created_files.items()
    )


class LiteratureSearchParams(NamedTuple):
    total: int
    minimal_influence: int
    distribution_factor: Optional[float]
    sort_by_similarity: bool

    def to_dict(self) -> dict:
        return self._asdict()


STAGE_AND_SCOPE_TO_LITERATURE_SEARCH_PARAMS: Dict[Tuple[str, str], LiteratureSearchParams] = {

    ('goal', 'dataset'): LiteratureSearchParams(12, 2, 2.0, False),
    ('goal', 'questions'): LiteratureSearchParams(12, 2, 2.0, False),
    ('goal', 'goal and hypothesis'): LiteratureSearchParams(10, 0, 1, False),

    ('writing', 'background'): LiteratureSearchParams(12, 5, 2.0, True),
    ('writing', 'dataset'): LiteratureSearchParams(12, 2, 2.0, False),
    ('writing', 'methods'): LiteratureSearchParams(6, 10, 1.5, False),
    ('writing', 'results'): LiteratureSearchParams(12, 1, 2.0, True),

}


DEFAULT_LITERATURE_SEARCH_STYLE = Mutable('chatgpt')


@dataclass
class ScientificProducts(Products):
    """
    Contains the different scientific outcomes of the research.
    These outcomes are gradually populated, where in each step we get a new product based on previous products.
    """
    data_file_descriptions: DataFileDescriptions = field(default_factory=DataFileDescriptions)
    codes_and_outputs: Dict[str, CodeAndOutput] = field(default_factory=dict)
    research_goal: Optional[str] = None
    literature_search: Dict[str, LiteratureSearch] = field(default_factory=dict)
    analysis_plan: Optional[str] = None
    hypothesis_testing_plan: Optional[Dict[str, str]] = None
    tables_names: Dict[str, str] = field(default_factory=dict)
    numeric_values: Dict[str, str] = field(default_factory=dict)
    results_summary: Optional[str] = None
    paper_sections_and_optional_citations: Dict[str, Union[str, Tuple[str, Set[Citation]]]] = \
        field(default_factory=MemoryDict)

    @property
    def tables(self) -> Dict[str, List[str]]:
        """
        Return the tables.
        """
        return {'results': [content for file, content
                            in self.codes_and_outputs['data_analysis'].get_created_content_files_to_contents().items()
                            if file.endswith('.tex')]}

    @property
    def pretty_hypothesis_testing_plan(self) -> str:
        """
        Return the hypothesis testing plan in a pretty way.
        """
        return '\n'.join(f'Hypothesis: {hypothesis}\nStatistical Test: {test}\n'
                         for hypothesis, test in self.hypothesis_testing_plan.items())

    @property
    def pretty_tables_names(self) -> str:
        """
        Return the tables names in a pretty way.
        """
        return '\n'.join(f'({table_num + 1}) "{table_name}"'
                         for table_num, table_name in enumerate(self.tables_names.values()))

    def get_tables_names_and_content(self) -> str:
        """
        Return the tables names and content.
        """
        s = 'We are creating a total of {} tables:\n\n'.format(len(self.tables_names))
        tables = self.tables['results']
        for i, (table_num, table_name) in enumerate(self.tables_names.items()):
            s += f'{table_num}: "{table_name}":\n'
            if i < len(tables):
                s += f'{tables[i]}'
            else:
                s += f'Not created yet.'
            s += '\n\n'
        return s

    @property
    def all_tables(self) -> List[str]:
        """
        Return the tables from all sections.
        """
        return [table for tables in self.tables.values() for table in tables]

    @property
    def all_file_descriptions(self) -> DataFileDescriptions:
        """
        Return the description of all files.
        """
        desc = DataFileDescriptions.from_other(self.data_file_descriptions)
        for code_and_output in self.codes_and_outputs.values():
            if code_and_output.description_of_created_files is not None:
                desc += code_and_output.description_of_created_files
            else:
                desc += [DataFileDescription(file_path=created_file)
                         for created_file in code_and_output.get_created_data_files()]
        desc.data_folder = self.data_file_descriptions.data_folder
        return desc

    def get_file_headers(self, code_step: str):
        """
        Return the file headers of a given code_step.
        """
        code_and_output = self.codes_and_outputs[code_step]
        created_files = code_and_output.get_created_data_files()
        if not created_files:
            return None
        return DataFileDescriptions(
            [DataFileDescription(file_path=created_file) for created_file in created_files],
            data_folder=self.data_file_descriptions.data_folder)

    @property
    def paper_sections_and_citations(self) -> Dict[str, Tuple[str, Set[Citation]]]:
        section_names_to_sections_and_citations = {}
        for section_name, section_and_optional_citations in self.paper_sections_and_optional_citations.items():
            if isinstance(section_and_optional_citations, str):
                section_names_to_sections_and_citations[section_name] = (section_and_optional_citations, set())
            else:
                section_names_to_sections_and_citations[section_name] = section_and_optional_citations
        return section_names_to_sections_and_citations

    @property
    def paper_sections_without_citations(self) -> Dict[str, str]:
        return {section_name: section
                for section_name, (section, citation) in self.paper_sections_and_citations.items()}

    @property
    def citations(self) -> NiceList[CrossrefCitation]:
        """
        Return the citations of the paper.
        """
        citations = ListBasedSet()
        for section_content, section_citations in self.paper_sections_and_citations.values():
            citations.update(section_citations)
        return NiceList(citations, separator='\n\n')

    @property
    def tabled_paper_sections(self) -> Dict[str, str]:
        """
        Return the actual tabled paper sections.
        """
        return {section_name: section if section_name not in self.tables
                else add_tables_to_paper_section(section, self.tables[section_name])
                for section_name, section in self.paper_sections_without_citations.items()}

    def get_title(self) -> str:
        """
        Return the title of the paper.
        """
        latex = self.paper_sections_without_citations['title']
        return extract_latex_section_from_response(latex, 'title', keep_tags=False)

    def get_abstract(self) -> str:
        """
        Return the abstract of the paper.
        """
        latex = self.paper_sections_without_citations['abstract']
        return extract_latex_section_from_response(latex, 'abstract', keep_tags=False)

    def _get_generators(self) -> Dict[str, NameDescriptionStageGenerator]:
        return {
            **super()._get_generators(),

            # DATA
            # ====

            'general_dataset_description': NameDescriptionStageGenerator(
                'Overall Description of the Dataset',
                'OVERALL DESCRIPTION OF THE DATASET\n\n{}',
                ScientificStages.DATA,
                lambda: self.data_file_descriptions.general_description,
            ),

            'data_file_descriptions': NameDescriptionStageGenerator(
                'Description of the Original Dataset',
                'DESCRIPTION OF THE ORIGINAL DATASET\n\n{}',
                ScientificStages.DATA,
                lambda: self.data_file_descriptions,
            ),

            'all_file_descriptions': NameDescriptionStageGenerator(
                'Description of the Dataset',
                'Description of the Dataset:\n\n{}',
                ScientificStages.DATA,
                lambda: self.all_file_descriptions,
            ),

            # GOAL AND PLAN
            # ==============

            'research_goal': NameDescriptionStageGenerator(
                'Research Goal',
                'Here is our Research Goal\n\n{}',
                ScientificStages.GOAL,
                lambda: self.research_goal,
            ),

            'analysis_plan': NameDescriptionStageGenerator(
                'Data Analysis Plan',
                'Here is our Data Analysis Plan:\n\n{}',
                ScientificStages.PLAN,
                lambda: self.analysis_plan,
            ),

            'hypothesis_testing_plan': NameDescriptionStageGenerator(
                'Hypothesis Testing Plan',
                'Here is our Hypothesis Testing Plan:\n\n{}',
                ScientificStages.PLAN,
                lambda: str(self.pretty_hypothesis_testing_plan),
            ),

            # LITERATURE SEARCH
            # =================

            'literature_search:{}:{}': NameDescriptionStageGenerator(
                '{name}',
                '{description}',
                ScientificStages.WRITING,
                lambda stage, scope: {
                    'name': self['literature_search:{}:{}:{}'.format(
                        stage, scope, DEFAULT_LITERATURE_SEARCH_STYLE.val)].name,
                    'description': self['literature_search:{}:{}:{}'.format(
                        stage, scope, DEFAULT_LITERATURE_SEARCH_STYLE.val)].description,
                }
            ),

            'literature_search:{}:{}:{}': NameDescriptionStageGenerator(
                '{scope}-related Literature Search',
                'Here are citations from our Literature Search for papers related to the {scope} of our study:\n\n'
                '{papers}',
                ScientificStages.WRITING,
                lambda stage, scope, style: {
                    'scope': scope.title(),
                    'papers': self.literature_search[stage].pretty_repr_for_scope_and_query(
                        scope=scope,
                        style=style,
                        **STAGE_AND_SCOPE_TO_LITERATURE_SEARCH_PARAMS[(stage, scope)].to_dict()
                    ),
                }
            ),

            'scope_and_literature_search': NameDescriptionStageGenerator(
                'Scope and Literature Search',
                'Here is a draft of the abstract, written as a basis for the literature search below:\n\n'
                '{title}\n\n{abstract}\n\n'
                'LITERATURE SEARCH\n\n'
                'We searched for papers related to the Background, Dataset, Methods, and Results of our paper. \n\n'
                '```html\n{background}\n```\n\n'
                '```html\n{dataset}\n```\n\n'
                '```html\n{methods}\n```\n\n'
                '```html\n{results}\n```\n\n',
                ScientificStages.LITERATURE_REVIEW_AND_SCOPE,
                lambda: {
                    'title': self.get_title(),
                    'abstract': self.get_abstract(),
                    'background': self['literature_search:writing:background:html'].description,
                    'dataset': self['literature_search:writing:dataset:html'].description,
                    'methods': self['literature_search:writing:methods:html'].description,
                    'results': self['literature_search:writing:results:html'].description,
                },
            ),

            # CODE
            # ====

            'codes:{}': NameDescriptionStageGenerator(
                '{code_name} Code',
                'Here is our {code_name} Code:\n```python\n{code}\n```\n',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {'code': self.codes_and_outputs[code_step].code,
                                   'code_name': self.codes_and_outputs[code_step].name},
            ),

            'outputs:{}': NameDescriptionStageGenerator(
                'Output of the {code_name} Code',
                'Here is the Output of our {code_name} code:\n```output\n{output}\n```\n',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {'output': self.codes_and_outputs[code_step].get_single_output(is_clean=True),
                                   'code_name': self.codes_and_outputs[code_step].name},
            ),

            'code_explanation:{}': NameDescriptionStageGenerator(
                '{code_name} Code Description',
                'Here is an explanation of our {code_name} code:\n\n{code_explanation}',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {
                    'code_name': self.codes_and_outputs[code_step].name,
                    'code_explanation': self.codes_and_outputs[code_step].code_explanation},
            ),

            'codes_and_outputs:{}': NameDescriptionStageGenerator(
                '{code_name} Code and Output',
                '{code_description}\n\n{output_description}',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {
                    'code_name': self.codes_and_outputs[code_step].name,
                    'code_description': self.get_description("codes:" + code_step),
                    'output_description': self.get_description("outputs:" + code_step)},
            ),

            'codes_and_outputs_with_explanations:{}': NameDescriptionStageGenerator(
                '{code_name} Code and Output',
                '{code_description}\n\n{output_description}\n\n{code_explanation}',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {
                    'code_name': self.codes_and_outputs[code_step].name,
                    'code_description': self.get_description("codes:" + code_step),
                    'output_description': self.get_description("outputs:" + code_step),
                    'code_explanation': self.get_description("code_explanation:" + code_step)},
            ),

            'created_files:{}': NameDescriptionStageGenerator(
                'Files Created by the {code_name} Code',
                'Here are the files created by the {code_name} code:\n\n{created_files}',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {
                    'created_files': self.codes_and_outputs[code_step].get_created_data_files(),
                    'code_name': self.codes_and_outputs[code_step].name},
            ),

            'created_files_description:{}': NameDescriptionStageGenerator(
                'Description of Files Created by the {code_name} Code',
                'We can use these files created by the {code_name} code:\n\n{created_files_description}',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {
                    'created_files_description': DataFileDescriptions(
                        self.data_file_descriptions + self.codes_and_outputs[code_step].description_of_created_files,
                        data_folder=self.codes_and_outputs[code_step].description_of_created_files.data_folder)
                    if self.codes_and_outputs[code_step].description_of_created_files is not None else None,
                    'code_name': self.codes_and_outputs[code_step].name},
            ),

            'created_files_headers:{}': NameDescriptionStageGenerator(
                'Headers of Files Created by the {code_name} Code',
                'Here are the headers of the files created by the {code_name} code:\n\n{created_files_headers}',
                lambda code_step: get_code_stage(code_step),
                lambda code_step: {
                    'created_files_headers': self.get_file_headers(code_step),
                    'code_name': self.codes_and_outputs[code_step].name},
            ),

            # WRITING
            # =======

            'results_summary': NameDescriptionStageGenerator(
                'Results Summary',
                'Here is our Results Summary:\n\n{}',
                ScientificStages.INTERPRETATION,
                lambda: self.results_summary,
            ),

            'title_and_abstract': NameDescriptionStageGenerator(
                'Title and Abstract',
                "Here are the title and abstract of the paper:\n\n{}\n\n{}",
                ScientificStages.WRITING_TITLE_AND_ABSTRACT,
                lambda: (self.paper_sections_without_citations['title'],
                         self.paper_sections_without_citations['abstract']),
            ),

            'most_updated_paper': NameDescriptionStageGenerator(
                'Most Updated Draft of the Paper',
                '{}',
                ScientificStages.WRITING,
                lambda: '\n\n'.join(self.tabled_paper_sections.values())
            ),

            'paper_sections:{}': NameDescriptionStageGenerator(
                '{section_name} Section of the Paper',
                'Here is the {section_name} section of the paper:\n\n{content}',
                lambda section_name: SECTION_NAMES_TO_WRITING_STAGES[section_name],
                lambda section_name: {'section_name': section_name.title(),
                                      'content': self.paper_sections_without_citations[section_name],
                                      },
            ),

            'tabled_paper_sections:{}': NameDescriptionStageGenerator(
                '{section_name} Section of the Paper with Tables',
                'Here is the {section_name} section of the paper with tables:\n\n{content}',
                ScientificStages.TABLES,
                lambda section_name: {'section_name': section_name.title(),
                                      'content': self.tabled_paper_sections[section_name],
                                      },
            ),

            'tables_names': NameDescriptionStageGenerator(
                'Captions of the Tables for the Paper',
                'Here are the Captions of the Tables for the Paper:\n\n{}',
                ScientificStages.TABLES,
                lambda: None if not self.tables_names else self.pretty_tables_names,
            ),

            'tables': NameDescriptionStageGenerator(
                'Tables of the Paper',
                'Here are the tables created by our data analysis code:\n\n{}',
                ScientificStages.TABLES,
                lambda: None if not self.all_tables else
                '\n\n'.join([f'- "{get_table_caption(table)}":\n\n```latex\n{table}\n```' for table in self.all_tables]),
            ),

            'tables_and_tables_names': NameDescriptionStageGenerator(
                'Tables of the Paper',
                '{tables}',
                ScientificStages.TABLES,
                lambda: {'tables': self.get_tables_names_and_content()}),

            'results_file': NameDescriptionStageGenerator(
                'Other Numeric Values for the Paper',
                'Here is the content of the "results.txt" file providing some additional numeric values '
                'we can use to write the results of the paper:\n\n{}',
                ScientificStages.CODE,
                lambda: self.codes_and_outputs['data_analysis'].get_created_content_files_to_contents()['results.txt']
            ),

            'numeric_values': NameDescriptionStageGenerator(
                'Other Numeric Values for the Paper',
                'Here are some other numeric values we can use to write the results of the paper:\n\n{}',
                ScientificStages.INTERPRETATION,
                lambda: None if not self.numeric_values else
                NiceList([f"({i + 1}) {numeric_value_name}:\n {numeric_value_content}"
                          for i, (numeric_value_name, numeric_value_content) in
                          enumerate(self.numeric_values.items())],
                         separator='\n\n'),
            ),

            'tables_and_numeric_values': NameDescriptionStageGenerator(
                'Tables and Numeric Values of the Paper',
                '{tables}\n\n{numeric_values}',
                ScientificStages.INTERPRETATION,
                lambda: {'tables': self.get_description('tables'),
                         'numeric_values': self.get_description('numeric_values')},
            ),
        }
