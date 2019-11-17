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


# We don't need to translate the external addresses, because the referenced accounts
# already have a mapping to a pycroft user
@reg.provides(pycroft_model.Address)
@reg.provides(pycroft_model.Room)
def translate_locations(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []
    accesses: List[abe_model.Access] = (
        ctx.query(abe_model.Access).filter(abe_model.Access.building != None).all()
    )

    for access in accesses:
        try:
            pycroft_building = data.buildings[access.building.short_name]
        except KeyError:
            ctx.logger.error("Could not find building data for shortname %s",
                             access.building.short_name)
            raise

        # consolidate nomecnlature
        level = access.floor
        room_number = f"{access.flat}{access.room}"
        address = pycroft_model.Address(
            street=access.building.street,
            number=access.building.number,
            zip_code=access.building.zip_code,
            addition=f"{level}-{room_number}"
        )
        objs.append(address)
        room = pycroft_model.Room(
            building=pycroft_building,
            inhabitable=True,
            level=level,
            number=room_number,
            address=address
        )
        objs.append(room)
        data.access_rooms[access.id] = room

    return objs
