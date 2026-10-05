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
