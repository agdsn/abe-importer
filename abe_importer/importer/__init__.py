from collections import Counter
from logging import Logger

from sqlalchemy.orm import Session

from pycroft.model import _all as pycroft_model
from abe_importer.importer.object_registry import ObjectRegistry
from . import translations  # executes the registration decorators
from .context import Context, IntermediateData, reg
from .tools import TranslationRegistry


def do_import(abe_session: Session, logger: Logger):
    logger.info("Starting (dummy) import")
    ctx = Context(abe_session, logger)
    data = IntermediateData()
    objs = ObjectRegistry(f"{logger.name}.object_reg")
    objs.add_filter(lambda o: isinstance(o, pycroft_model.Building) and o.number == '50')
    objs.add_filter(lambda o: isinstance(o, pycroft_model.Address) and o.addition.endswith('-13'))
    objs.add_filter(lambda o: isinstance(o, pycroft_model.Address) and o.addition.endswith('-13'))

    for func in reg.sorted_functions():
        logger.info(f"  {func.__name__}...")

        new_objects = func(ctx, data)

        obj_counter = Counter((type(ob).__name__ for ob in new_objects))
        details = ", ".join([f"{obj}: {num}" for obj, num in obj_counter.items()])
        logger.info(f"  ...{func.__name__} ({details}).")
        objs.extend(new_objects)
        objs.flush()

    return objs
