## 2024-05-01 - Icon-Only Buttons Require Accessible Names
**Learning:** In PySide6/PyQt desktop applications, using `setToolTip` on an icon-only `QPushButton` is insufficient for screen readers. The tooltip helps sighted users, but assistive technology relies on the accessible name for context.
**Action:** Always call `.setAccessibleName("Description")` alongside `.setToolTip("Description")` when creating icon-only interactive UI elements in PySide6 applications.
