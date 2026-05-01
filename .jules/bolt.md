## 2025-03-01 - Bounding Box Alpha Compositing

**Learning:** When using PIL (`Pillow`), `alpha_composite` over a full-screen transparent image is significantly slower than cropping the overlay to its non-transparent bounding box (`getbbox()`) and alpha compositing just that region using an offset `(x, y)`. Full screen composites were taking ~9s for 10,000 iterations, whereas bounded composites took ~1.5s (a ~6x performance improvement). Also, using direct attribute access on objects with a defined set of default attributes is faster than `getattr`.

**Action:** When creating layers or caching rendered UI elements in Python with PIL, always use `getbbox()` to find the active region and composite only that smaller area to the base canvas rather than relying on full-canvas transparent overlays.

## 2023-10-25 - Transparent Bbox Short-Circuiting
**Learning:** When optimizing Pillow's `alpha_composite` by using a bounded crop, if the overlay image is completely transparent (i.e. `getbbox()` returns `None`), falling back to `base.alpha_composite(overlay)` is unnecessary. Compositing a fully transparent image has no visual effect but still incurs a performance penalty as Pillow processes the pixels.
**Action:** When using a custom bounded `alpha_composite` helper, short-circuit the operation entirely by using `pass` or `return` when `bbox` is `None` rather than falling back to the unoptimized full-screen composite.
## 2024-05-24 - Group Name Mapping Optimization
**Learning:** In element duplication loops, iterating over elements repeatedly to collect properties before performing operations introduces unnecessary O(N) overhead. Furthermore, checking if a generated name exists in a dict's `.values()` inside a while loop turns name generation into an O(N^2) operation, causing massive performance drops.
**Action:** When mapping unique properties (like group names) during duplication, populate mapping dictionaries lazily in a single iteration pass. Also ensure that when adding items, use $O(1)$ lookups in a pre-populated `set` rather than scanning `.values()` of dicts repeatedly.
