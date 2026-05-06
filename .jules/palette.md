## 2024-05-06 - Accessible Checkboxes and QAction Limitations
**Learning:** Overriding the accessible name of a `QCheckBox` using `setAccessibleName` hides its visual label from screen readers (violating WCAG 2.5.3). `QAction` objects do not support `setAccessibleName` in PySide6 and will crash if called.
**Action:** Use `setAccessibleDescription` to append supplementary text to widgets that already have a primary text label. Avoid accessibility method calls on `QAction` instances.
