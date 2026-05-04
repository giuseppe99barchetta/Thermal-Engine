## 2024-10-25 - PyQt/PySide6 accessibility for icon-only buttons
**Learning:** PySide6 `QPushButton` instances used solely to display icons, colors, or visual formatting elements without text strings (like `B` or `I` for formatting, or `...` for file browsing) are completely unreadable to screen readers and difficult to understand visually without labels.
**Action:** When adding or auditing icon-only buttons in PySide6/PyQt applications, always use both `setToolTip()` for visual mouse users and `setAccessibleName()` for screen reader accessibility to ensure full usability.
