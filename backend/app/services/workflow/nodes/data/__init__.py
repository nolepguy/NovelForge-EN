# All Data nodes have been removed.
# In code-based workflows, these features can be replaced with Python expressions:
# - Data.ExtractPath -> direct attribute access: novel.chapter_list
# - Data.Text -> string literal: "Hello World"
# - Data.Log -> Python logger: logger.info(...)
# - Data.Reduce -> Python reduce/sum: sum(numbers)
# - Data.GenerateRange -> range + list comprehension: [{"index": i} for i in range(n)]
# - Data.Group -> groupby/dict comprehension: {k: list(v) for k, v in groupby(...)}

__all__ = []