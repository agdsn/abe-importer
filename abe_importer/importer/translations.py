from typing import List

from pycroft.model import _all as pycroft_model

from .. import model as abe_model
from .context import reg, IntermediateData, Context


@reg.provides(pycroft_model.Site)
def add_sites(_, data: IntermediateData):
    site = pycroft_model.Site(name="Hochschulstraße")
    data.hss_site = site
    return [site]


PycroftBase = pycroft_model.ModelBase


@reg.provides(pycroft_model.Building)
def translate_building(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []

    buildings: List[abe_model.Building] = ctx.query(abe_model.Building).all()
    for b in buildings:
        ctx.logger.debug(f"got building {b.short_name!r}")
        new_building = pycroft_model.Building(
            short_name=b.short_name,
            street=b.street,
            number=b.number,
        )
        data.buildings[b.short_name] = new_building
        objs.append(new_building)

    return objs
