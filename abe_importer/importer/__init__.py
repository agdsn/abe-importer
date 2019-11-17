from collections import Counter
from logging import Logger

from sqlalchemy.orm import Session

from . import translations  # executes the registration decorators
from .context import Context, IntermediateData, reg
from .tools import TranslationRegistry


def do_import(abe_session: Session, logger: Logger):
    logger.info("Starting (dummy) import")
    ctx = Context(abe_session, logger)
    data = IntermediateData()
    objs = []

    for func in reg.sorted_functions():
        logger.info(f"  {func.__name__}...")

        new_objects = func(ctx, data)

        obj_counter = Counter((type(ob).__name__ for ob in new_objects))
        details = ", ".join([f"{obj}: {num}" for obj, num in obj_counter.items()])
        logger.info(f"  ...{func.__name__} ({details}).")
        objs.extend(new_objects)

    return objs


