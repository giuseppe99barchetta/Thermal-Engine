## 2025-03-01 - Bounding Box Alpha Compositing

**Learning:** When using PIL (`Pillow`), `alpha_composite` over a full-screen transparent image is significantly slower than cropping the overlay to its non-transparent bounding box (`getbbox()`) and alpha compositing just that region using an offset `(x, y)`. Full screen composites were taking ~9s for 10,000 iterations, whereas bounded composites took ~1.5s (a ~6x performance improvement). Also, using direct attribute access on objects with a defined set of default attributes is faster than `getattr`.

**Action:** When creating layers or caching rendered UI elements in Python with PIL, always use `getbbox()` to find the active region and composite only that smaller area to the base canvas rather than relying on full-canvas transparent overlays.

## 2023-10-25 - Transparent Bbox Short-Circuiting
**Learning:** When optimizing Pillow's `alpha_composite` by using a bounded crop, if the overlay image is completely transparent (i.e. `getbbox()` returns `None`), falling back to `base.alpha_composite(overlay)` is unnecessary. Compositing a fully transparent image has no visual effect but still incurs a performance penalty as Pillow processes the pixels.
**Action:** When using a custom bounded `alpha_composite` helper, short-circuit the operation entirely by using `pass` or `return` when `bbox` is `None` rather than falling back to the unoptimized full-screen composite.

## 2024-05-18 - QTreeWidget topLevelItemCount micro-optimization
**Learning:** Evaluated `topLevelItemCount()` once before passing it into `range()` inside `src/ui/element_list.py` to prevent any possibility of redundant property access during loop construction. While Python evaluates `range()` arguments exactly once upon loop start naturally, pre-evaluating widget properties provides a consistent structure and addresses specific perceived inefficiencies in legacy loops.
**Action:** When iterating over QTreeWidget elements, cache property accesses like `topLevelItemCount()` outside loops or `range()` calls for consistency and slightly stricter semantic correctness, avoiding property getter calls directly as arguments where unnecessary.
