"""Edit one conditional display rule using the existing property undo flow."""
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox
from src.core.constants import SOURCE_UNITS
from src.core.conditions import ACTIONS, COMPARISONS
from src.core.security import validate_element_schema


class ConditionDialog(QDialog):
    def __init__(self, rule, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conditional rule")
        self.resize(420, 280)
        form = QFormLayout(self)
        self.enabled = QCheckBox("Enable rule")
        self.enabled.setChecked(bool(rule))
        form.addRow(self.enabled)
        self.source = QComboBox()
        for key, info in SOURCE_UNITS.items():
            if key != "static":
                self.source.addItem(f"{info['name']} ({key})", key)
        source = rule.get("source", "cpu_temp")
        if self.source.findData(source) < 0:
            self.source.addItem(source, source)
        self.source.setCurrentIndex(self.source.findData(source))
        form.addRow("Source", self.source)
        self.comparison = QComboBox()
        self.comparison.addItems(COMPARISONS)
        self.comparison.setCurrentText(rule.get("operator", ">"))
        form.addRow("Comparison", self.comparison)
        self.value = QLineEdit(str(rule.get("value", "80")))
        self.value.setToolTip("Number, exact text, or true/false for boolean sensors")
        form.addRow("Value", self.value)
        self.action = QComboBox()
        for action, label in zip(ACTIONS, ("Change color", "Change text", "Show only when matched", "Hide when matched")):
            self.action.addItem(label, action)
        self.action.setCurrentIndex(max(0, self.action.findData(rule.get("action", "color"))))
        form.addRow("Action", self.action)
        self.color = QLineEdit(rule.get("color", "#ff4444"))
        form.addRow("Color", self.color)
        self.text = QLineEdit(rule.get("text", ""))
        form.addRow("Text", self.text)
        self.action.currentIndexChanged.connect(self._update_rows)
        self._update_rows()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _update_rows(self):
        self.layout().setRowVisible(self.color, self.action.currentData() == "color")
        self.layout().setRowVisible(self.text, self.action.currentData() == "text")

    def rule(self):
        return {"source": self.source.currentData(), "operator": self.comparison.currentText(),
                "value": self.value.text(), "action": self.action.currentData(),
                "color": self.color.text(), "text": self.text.text()} if self.enabled.isChecked() else {}

    def _accept(self):
        errors = validate_element_schema({"type": "text", "condition": self.rule()}, 0)
        if errors:
            QMessageBox.warning(self, "Invalid rule", "\n".join(errors))
            return
        self.accept()
