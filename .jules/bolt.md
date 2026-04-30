## 2025-03-01 - Bounding Box Alpha Compositing

**Learning:** When using PIL (`Pillow`), `alpha_composite` over a full-screen transparent image is significantly slower than cropping the overlay to its non-transparent bounding box (`getbbox()`) and alpha compositing just that region using an offset `(x, y)`. Full screen composites were taking ~9s for 10,000 iterations, whereas bounded composites took ~1.5s (a ~6x performance improvement). Also, using direct attribute access on objects with a defined set of default attributes is faster than `getattr`.

**Action:** When creating layers or caching rendered UI elements in Python with PIL, always use `getbbox()` to find the active region and composite only that smaller area to the base canvas rather than relying on full-canvas transparent overlays.
