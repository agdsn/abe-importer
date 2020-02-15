from dataclasses import dataclass, field
from logging import Logger
from typing import Dict, Callable, List, Any

from pycroft.model import _all as pycroft_model
from sqlalchemy.orm import Session, Query

from .tools import TranslationRegistry


@dataclass
class Context:
    abe_session: Session
    pycroft_session: Session
    logger: Logger

    def query(self, *entities: Any, **kwargs: Any) -> Query:
        return self.abe_session.query(*entities, **kwargs)


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

    # switch_name → Switch
    switches: Dict[str, pycroft_model.Switch] = dict_field()

    # account-name → User
    users: Dict[str, pycroft_model.User] = dict_field()


reg: TranslationRegistry[
    Callable[[Context, IntermediateData], List[pycroft_model.ModelBase]],
    pycroft_model.ModelBase
] \
    = TranslationRegistry()
