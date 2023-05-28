from dataclasses import dataclass
from typing import Optional, Set

from scientistgpt.run_gpt_code.overrides.override_dataframe import DataframeOperations


@dataclass
class CodeAndOutput:
    name: str = None
    code: str = None
    output: str = None
    output_file: Optional[str] = None
    created_files: Set[str] = None
    code_name: str = None
    explanation: Optional[str] = None
    dataframe_operations: Optional[DataframeOperations] = None

    def get_created_files_beside_output_file(self) -> Set[str]:
        if self.created_files is None:
            return set()
        return self.created_files - {self.output_file}
