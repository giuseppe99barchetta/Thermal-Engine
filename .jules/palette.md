## 2024-05-01 - Icon-Only Buttons Require Accessible Names
**Learning:** In PySide6/PyQt desktop applications, using `setToolTip` on an icon-only `QPushButton` is insufficient for screen readers. The tooltip helps sighted users, but assistive technology relies on the accessible name for context.
**Action:** Always call `.setAccessibleName("Description")` alongside `.setToolTip("Description")` when creating icon-only interactive UI elements in PySide6 applications.
## 2026-05-02 - Add Tooltips and Accessible Names to PySide6 Icon Buttons
**Learning:** In PySide6 applications, icon-only or visually ambiguous buttons (like pagination controls, add/remove buttons, etc.) are inaccessible to screen readers and lack context for sighted users. The convention is to use `setToolTip()` for hover context and `setAccessibleName()` (Qt's equivalent to ARIA labels) for screen readers.
**Action:** When adding or modifying interactive UI elements in PySide6, always ensure that any icon-only button, or button whose text is not fully descriptive (like '+ New' or '...'), includes both a descriptive tooltip and an accessible name.
## 2024-05-18 - Added Tooltips and Accessible Names to UI Properties
**Learning:** Some elements in `src/ui/properties.py` are visually ambiguous or only display an icon, making them inaccessible for screen readers, and lacking context for sighted users.
**Action:** Always verify that interactive elements, especially icon-only buttons, have `setAccessibleName` for screen readers and `setToolTip` for sighted users when adding or modifying them.
## 2024-10-25 - PyQt/PySide6 accessibility for icon-only buttons
**Learning:** PySide6 `QPushButton` instances used solely to display icons, colors, or visual formatting elements without text strings (like `B` or `I` for formatting, or `...` for file browsing) are completely unreadable to screen readers and difficult to understand visually without labels.
**Action:** When adding or auditing icon-only buttons in PySide6/PyQt applications, always use both `setToolTip()` for visual mouse users and `setAccessibleName()` for screen reader accessibility to ensure full usability.
