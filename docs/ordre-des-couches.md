# Layer order

The order of the layer list, on the left of the map, is set in the Django admin
(<http://localhost:8000/admin/>), on two pages. Nothing needs to be added: each
page already lists everything. Change the numbers of the **Order** column, on as
many rows as needed, click **Save** at the bottom of the list, then reload the map.

| Page | What it orders |
|---|---|
| **Commons › Layer groups** | the sections: Summary per grid cell, Traffic, Biodiversity, Outdoor, External layers |
| **Commons › Layer orders** | the layers within their section, listed by section |

The smallest number comes first. A layer always stays in its section. Ranks are
spaced by 10, so that an item can be put between two others (e.g. 15 between 10
and 20).

A new layer (counting object type, external layer) appears at the end of its
section the next time **Layer orders** is opened; a deleted layer disappears.
