# Lines of Empire

Intended to be an improved clone of the mobile game European War 3.

## Context and vision

European War 3 starts with a standard European map that you would find in any
atlas, and divides it into many smaller irregularly shaped regions, where the
player can move its pieces. The regions are just the perfect size: not too small
that it goes down to the tactical level, not too big that it starts resembling
classic Risk, but just the right size to bring the game to the strategic level.

The irregularity of the regions contributes to the visual appeal of the map.
Other games represent the map as a tiling of hexagonal cells. This makes it
easier to create such maps, but it comes at the cost of cartographic beauty.
Therefore, European War 3 gets the map just right.

However, one limitation that the game has is that it only allows the player to
move pieces within one of several limited theaters: Europe, North America, and
East Asia. These regions are disconnected from each other. What's more, the
regions are defined on a flat map projection rather than on a true globe. So
north-south distortion is not accounted for.

Therefore, my vision for Lines of Empire is to have a single unified global
theater, using a true globe model, with regions at just the right size to matter
at the strategic level. The globe will be shown in an orthographic or
stereographic projection in order to preserve the true spherical nature of the
earth.

The ideal size of each region should be based upon the concept of "strategic
depth". A theater like Europe should contain smaller regions, since most of them
are historically contested, contain significant infrastructure and urban
development, and are relatively dense with population. But a theater like the
Amazon rainforest or the Sahara desert should be lumped together into bigger
regions because most of the land is not strategically interesting enough to
matter. Open plains should also be lumped into bigger regions, because a unit
has more ease of movement. A region like the Caucasus should be divided into
smaller regions because the Caucasus is very demographically diverse, and has
many valleys where troops can occupy. But a region like Tibet may be allowed to
have larger regions because it is not that populous.

Regardless of the size of each region, it may be beneficial to let each region
have its own penalty for movement: mountains and rainforests may penalize troop
movement through them, while open plains have a smaller penalty.

Once this map system is in place, it becomes possible to train various AI's to
compete against each other in the global theater.



## What is needed to generate the regions

The maps in European War 3 seem to have been produced by taking a copy of a
real map of Europe, and manually tracing lines on it to divide it into regions.
But to do this in a global scale is a much more daunting task. And if you wish
to edit any regions, you have to do it manually.

In order to create the regions, we may employ a
[Voronoi algorithm](https://en.wikipedia.org/wiki/Voronoi_diagram)
that draws the regions based on the positions of various seed points. The seed
points can then be scattered across the globe according to a desired density.
Then, we can use
[Lloyd relaxation](https://en.wikipedia.org/wiki/Lloyd%27s_algorithm)
to make the regions have a fairly uniform size.

But this method is not enough. A Voronoi algorithm creates neat polygonal
regions. But the regions in European War 3 are irregular in shape, and often
times anchor their borders on geographic features such as rivers or coastlines.
Therefore, the algorithm for generating regions must have some knowledge of
geographic or political features on the map.



## Core economy

The economy is intentionally simplified into four universal resources:

- **Food:** sustains populations and armies
- **Materials:** physical inputs for construction, equipment, and warfare
- **Wealth:** money, liquidity, taxation, commerce, purchasing power
- **Industry:** productive capacity, workshops, factories, shipyards,
infrastructure, etc.

These remain meaningful across all historical eras.



## Strategic Resources

Specific commodities are modeled as **strategic resources**, not additional
currencies.

Examples include:
- Horses
- Iron
- Coal
- Oil
- Uranium
- Rare earths

Technology determines which strategic resources matter. A resource may
physically exist on the map long before it becomes strategically important.

Strategic resources primarily provide **access conditions** rather than
stockpiles:

> None → Limited → Sufficient → Surplus

For example, an oil shortage might reduce mechanized movement, air
operations, and industrial efficiency without introducing a separate `Oil`
currency.


A country can obtain a strategic resource through domestic production or trade
access. Therefore, a state does not need to conquer every resource it requires.
This creates strategic dependencies: an industrial power may depend on foreign
oil, uranium, or rare-earth supplies.

## Trade

Trade is deliberately abstract.

- **Open trade:** normal commercial access
- **Limited trade:** reduced access due to sanctions, tariffs, poor relations,
etc.
- **Embargo:** deliberate cutoff of trade
- **Blockaded:** trade relationships may exist, but military control prevents
goods from reaching the country

This distinction allows both economic warfare and geographic warfare to matter
without simulating individual shipments.



## Cards

Cards represent major strategic interventions rather than routine economic management.

Examples:

- **Oil Embargo**
- **Strategic Reserve**
- **Synthetic Fuel**
- **Resource Agreement**
- **Lend-Lease**
- **Naval Blockade**
- **Break the Blockade**
- **Export Controls**
- **Close the Straits**
- **Strategic Bombing**

Cards should generally require appropriate world conditions. For example, an
**Oil Embargo** should only be available if the player actually supplies
meaningful oil to the target.



## Design Philosophy

Lines of Empire should model strategy, not tedious details of administration.

The player should decide:
- Which territories are worth fighting over?
- Which resources must be secured?
- Which trade routes must remain open?
- Which countries are dangerous dependencies?
- When is an embargo or blockade worth using?

They should **not** need to manage barrels of oil, tons of coal, freight
contracts, or individual commodity markets.
