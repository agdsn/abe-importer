from collections import Counter
from dataclasses import dataclass, field
from logging import Logger
from typing import Dict, List

from sqlalchemy.orm import Session
from pycroft.model import _all as pycroft_model

from abe_importer.model import Base
from .tools import TranslationRegistry
from . import model as abe_model


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


@dataclass
class Context:
    abe_session: Session
    logger: Logger


def dict_field():
    return field(default_factory=lambda: {})


@dataclass
class IntermediateData:
    hss_site: pycroft_model.Site = None

    # shortname → Building
    buildings: Dict[str, pycroft_model.Building] = dict_field()

    # An access results in a room
    access_rooms: Dict[int, pycroft_model.Room] = dict_field()
    account_external_address: Dict[str, pycroft_model.Address] = dict_field()


reg = TranslationRegistry()


@reg.provides(pycroft_model.Site)
def add_sites(_, data: IntermediateData):
    site = pycroft_model.Site(name="Hochschulstraße")
    data.hss_site = site
    return [site]


@reg.provides(pycroft_model.Building)
def translate_building(ctx: Context, data: IntermediateData) -> List[Base]:
    objs = []

    shortnames = ctx.abe_session.query(abe_model.Access.building).distinct()
    for s in shortnames:
        ctx.logger.debug(f"got shortname {s!r}")

    return objs


