import functools
from dataclasses import dataclass, field
from typing import List, Iterable

import numpy as np
import pandas as pd

from data_to_paper.run_gpt_code.base_run_contexts import RunContext
from data_to_paper.run_gpt_code.run_issues import CodeProblem, RunIssue
from data_to_paper.utils.mutable import Flag, Mutable
from data_to_paper.utils.operator_value import OperatorValue


class PValue(OperatorValue):
    """
    An object that represents a p-value float.
    """
    allow_str = Flag(False)
    error_message_on_forbidden_func = Mutable("Calling `{func_name}` on a PValue object is forbidden.\n")
    this_is_a_p_value = True

    def __init__(self, value, created_by: str = None):
        super().__init__(value)
        self.created_by = created_by

    def _forbidden_func(self, func):
        if self.allow_str:
            return func(self.value)
        raise RunIssue.from_current_tb(
                issue=self.error_message_on_forbidden_func.val.format(func_name=func.__name__,
                                                                      created_by=self.created_by),
                code_problem=CodeProblem.RuntimeError,
        )

    @property
    def __class__(self):
        if not self.allow_str:
            return type(self.value)
        return PValue

    def __str__(self):
        return self._forbidden_func('{:.4g}'.format)

    def __repr__(self):
        return self._forbidden_func('{:.4g}'.format)

    def __float__(self):
        return self._forbidden_func(float)

    @classmethod
    def from_value(cls, value, created_by: str = None, raise_on_nan: bool = True, func_call_str: str = None):
        if isinstance(value, cls):
            return value
        if raise_on_nan and np.isnan(value):
            call_str = f'\nThe function was called as: \n{func_call_str}\n\n' if func_call_str else ''
            raise RunIssue.from_current_tb(
                    issue=f'The function returned a p-value of NaN.\n{call_str}',
                    code_problem=CodeProblem.RuntimeError,
                    instructions='Please see if you understand why this is happening and fix it.',
            )
        return cls(value, created_by=created_by)

    @classmethod
    def reconstruction(cls, value, created_by):
        return cls(value, created_by)

    def __reduce__(self):
        return self.reconstruction, (self.value, self.created_by)


def convert_to_p_value(value, created_by: str = None, raise_on_nan: bool = True, func_call_str: str = None):
    if is_p_value(value):
        return value
    kwargs = dict(created_by=created_by, raise_on_nan=raise_on_nan, func_call_str=func_call_str)
    if isinstance(value, float):
        return PValue.from_value(value, **kwargs)
    if isinstance(value, np.ndarray):
        return np.vectorize(PValue.from_value)(value, **kwargs)
    if isinstance(value, pd.Series):
        return value.apply(functools.partial(PValue.from_value, **kwargs))
    if isinstance(value, list):
        return [convert_to_p_value(val, **kwargs) for val in value]
    if isinstance(value, dict):
        return {key: convert_to_p_value(val, **kwargs) for key, val in value.items()}


def is_p_value(value):
    return hasattr(value, 'this_is_a_p_value')


def is_containing_p_value(value):
    if is_p_value(value):
        return True
    if isinstance(value, np.ndarray):
        return np.any(np.vectorize(is_containing_p_value)(value))
    if isinstance(value, pd.Series):
        return value.apply(is_containing_p_value).any()
    if isinstance(value, pd.DataFrame):
        return value.applymap(is_containing_p_value).any().any()
    if isinstance(value, (list, tuple)):
        return any(is_containing_p_value(val) for val in value)
    if isinstance(value, dict):
        return any(is_containing_p_value(val) for val in value.values())
    return False


@dataclass
class TrackPValueCreationFuncs(RunContext):
    package_names: Iterable[str] = ()
    pvalue_creating_funcs: List[str] = field(default_factory=list)

    def _add_pvalue_creating_func(self, func_name: str):
        if self._is_enabled and self._is_called_from_user_script(4):
            self.pvalue_creating_funcs.append(func_name)