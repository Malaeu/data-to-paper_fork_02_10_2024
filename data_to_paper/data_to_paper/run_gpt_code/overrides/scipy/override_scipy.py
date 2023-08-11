import functools
import inspect
from dataclasses import dataclass

import scipy

from data_to_paper.run_gpt_code.overrides.attr_replacers import FuncReplacerContext

from ..types import PValue


@dataclass
class ScipyOverride(FuncReplacerContext):
    base_module: object = scipy

    @staticmethod
    def _should_replace(module, func_name, func) -> bool:
        doc = inspect.getdoc(func)
        if doc and "p-value" in doc:
            return True
        return False

    def custom_wrapper(self, original_func):

        @functools.wraps(original_func)
        def wrapped(*args, **kwargs):
            result = original_func(*args, **kwargs)

            # Replace the pvalues attribute if it exists
            try:
                asdict = {k.strip('_'): v for k, v in result._asdict().items()}
                if 'pvalue' in asdict:
                    asdict['pvalue'] = PValue.from_value(asdict['pvalue'], created_by=original_func.__name__)
                    result = type(result)(**asdict)
            except (AttributeError, TypeError, ValueError):
                pass
            return result

        return wrapped
