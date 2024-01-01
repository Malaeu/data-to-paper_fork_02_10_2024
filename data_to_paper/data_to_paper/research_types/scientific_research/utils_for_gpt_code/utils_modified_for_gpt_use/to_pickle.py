import numbers
from typing import Dict

import pandas as pd
from pandas.core.frame import DataFrame

from data_to_paper.run_gpt_code.base_run_contexts import RegisteredRunContext
from data_to_paper.run_gpt_code.overrides.attr_replacers import AttrReplacer
from data_to_paper.run_gpt_code.overrides.pvalue import PValue
from data_to_paper.run_gpt_code.types import RunIssue, CodeProblem, RunUtilsError

from .check_df_of_table import check_df_of_table_for_content_issues


def dataframe_to_pickle_with_checks(df: pd.DataFrame, path: str, *args,
                                    original_func=None, context_manager: AttrReplacer = None, **kwargs):
    """
    Save a data frame to a pickle file.
    Check for content issues.
    """
    if hasattr(context_manager, 'prior_tables'):
        prior_tables: Dict[str, pd.DataFrame] = context_manager.prior_tables
    else:
        prior_tables = {}
        context_manager.prior_tables = prior_tables
    prior_tables[path] = df

    # check that the df has only numeric, str, bool, or tuple values:
    for value in df.values.flatten():
        if isinstance(value, (pd.Series, pd.DataFrame)):
            context_manager.issues.append(RunIssue(
                item=path,
                issue=f"Something wierd in your dataframe. Iterating over df.values.flatten() "
                      f"returned a {type(value)} object.",
                code_problem=CodeProblem.OutputFileContentLevelA,
            ))
            break
        if not isinstance(value, (numbers.Number, str, bool, tuple, PValue)):
            context_manager.issues.append(RunIssue(
                item=path,
                issue=f"Your dataframe contains a value of type {type(value)} which is not supported. "
                      f"Please make sure the saved dataframes have only numeric, str, bool, or tuple values.",
                code_problem=CodeProblem.OutputFileContentLevelA,
            ))
            break

    if args or kwargs:
        raise RunUtilsError(run_issue=RunIssue(
            issue="Please use `to_pickle(path)` with only the `path` argument.",
            instructions="Please do not specify any other arguments.",
            code_problem=CodeProblem.RuntimeError,
        ))

    if not isinstance(path, str):
        raise RunUtilsError(run_issue=RunIssue(
            issue="Please use `to_pickle(filename)` with a filename as a string argument in the format 'table_x'",
            code_problem=CodeProblem.RuntimeError,
        ))
    context_manager.issues.extend(check_df_of_table_for_content_issues(df, path, prior_tables=prior_tables))
    with RegisteredRunContext.temporarily_disable_all(), PValue.allow_str.temporary_set(True):
        original_func(df, path)


def get_dataframe_to_pickle_attr_replacer():
    return AttrReplacer(obj_import_str='pandas.DataFrame', attr='to_pickle', wrapper=dataframe_to_pickle_with_checks,
                        send_context_to_wrapper=True, send_original_to_wrapper=True)


def pickle_dump_with_checks(obj, file, *args, original_func=None, context_manager: AttrReplacer = None, **kwargs):
    """
    Save a Dict[str, Any] to a pickle file.
    Check for content issues.
    """
    if args or kwargs:
        raise RunUtilsError(run_issue=RunIssue(
            issue="Please use `dump(obj, file)` with only the `obj` and `file` arguments.",
            instructions="Please do not specify any other arguments.",
            code_problem=CodeProblem.RuntimeError,
        ))

    # Check if the object is a dictionary
    if isinstance(obj, DataFrame):
        raise RunUtilsError(run_issue=RunIssue(
            issue="Please use `pickle.dump` only for saving the dictionary."
                  "Use `df.to_pickle(filename)` for saving the table dataframes.",
            code_problem=CodeProblem.RuntimeError,
        ))

    if not isinstance(obj, dict):
        raise RunUtilsError(run_issue=RunIssue(
            issue="Please use `pickle.dump` only for saving the dictionary `obj`.",
            code_problem=CodeProblem.RuntimeError,
        ))

    # Check if the keys are strings
    if not all(isinstance(key, str) for key in obj.keys()):
        context_manager.issues.append(RunIssue(
            issue="Please use `dump(obj, filename)` with a dictionary `obj` with string keys.",
            code_problem=CodeProblem.RuntimeError,
        ))
    with PValue.allow_str.temporary_set(True):
        original_func(obj, file)


def get_pickle_dump_attr_replacer():
    return AttrReplacer(obj_import_str='pickle', attr='dump', wrapper=pickle_dump_with_checks,
                        send_context_to_wrapper=True, send_original_to_wrapper=True)
