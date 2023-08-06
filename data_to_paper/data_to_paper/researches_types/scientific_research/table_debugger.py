from dataclasses import dataclass
from functools import partial
from typing import Optional, Tuple, List

from data_to_paper.base_steps import DebuggerConverser, CheckLatexCompilation
from data_to_paper.utils import dedent_triple_quote_str

from data_to_paper.run_gpt_code.types import ContentOutputFileRequirement, RunIssue, CodeProblem


@dataclass
class TablesDebuggerConverser(CheckLatexCompilation, DebuggerConverser):
    tolerance_for_too_wide_in_pts: Optional[float] = 25.
    headers_required_in_code: Tuple[str, ...] = (
        '# IMPORT',
        '# LOAD DATA',
        '# PREPROCESSING',
        '# ANALYSIS',
        '# CREATE TABLES',
        '# OUTPUT TEXT FILE',
    )

    def _get_runtime_available_objects(self) -> dict:
        return {'compile_to_pdf_func': partial(self._check_latex_compilation, is_table=True)}

    def _get_issues_for_static_code_check(self, code: str) -> List[RunIssue]:
        issues = super()._get_issues_for_static_code_check(code)

        for un_allowed_func in ['to_latex', 'as_latex']:
            if un_allowed_func + '(' in code:
                issues.append(RunIssue(
                    issue=f"It seems like you are using the `{un_allowed_func}` method.",
                    instructions=f"Please use the `to_latex_with_note` method instead.",
                    comment='Unallowed method used',
                    code_problem=CodeProblem.StaticCheck,
                ))

        return issues

    def _get_issues_for_output_file_content(self, requirement: ContentOutputFileRequirement,
                                            filename: str, content: str) -> List[RunIssue]:
        """
        We try to compile the table, and if it fails, we return an issue.
        """
        if not requirement.filename.endswith('.tex'):
            return super()._get_issues_for_output_file_content(requirement, filename, content)

        return []

