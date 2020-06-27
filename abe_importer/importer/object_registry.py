import logging
from collections import Counter
from typing import TypeVar, Hashable, Generic, List, Optional, Callable

T = TypeVar('T', bound=Hashable)


class ObjectRegistry(Generic[T]):
    """
    Basically an overcomplicated list to allow for debug introspection
    """
    objs: List[T]
    staging: List[T]
    logger: logging.Logger
    object_filters: List[Callable[[object], bool]]

    def __init__(self, logger_name: Optional[str] = None):
        self.object_filters = []
        self.objs = []
        self.staging = []
        self.logger = logging.getLogger(logger_name or 'object_registry')

    def append(self, value: T):
        self.insert_hook(value)
        self.staging.append(value)

    def extend(self, values: List[T]):
        for v in values:
            self.insert_hook(v)
        self.staging.extend(values)

    def flush(self):
        """Don't ask why this exists

        I thought we could try an early commit, but that turned out to be a stupid idea.
        """
        self.logger.debug(
            "Flushing %d records: %r",
            len(self.staging),
            Counter([type(o) for o in self.staging])
        )
        self.objs.extend(self.staging)
        self.staging.clear()

    def add_filter(self, f: Callable[[object], bool]):
        self.object_filters.append(f)

    def __iter__(self):
        if self.staging:
            raise RuntimeError(f"We still have {len(self.staging)} objects staged."
                               f" Please call flush before using the objects!")
        return iter(self.objs)

    def __len__(self):
        return len(self.objs)

    def insert_hook(self, value):
        if any(is_interesting(value) for is_interesting in self.object_filters):
            self.logger.info("Got interesting object %r", value)

