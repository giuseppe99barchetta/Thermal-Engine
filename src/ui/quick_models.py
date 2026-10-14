"""Small observable row models shared by the QML views."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QByteArray, Slot


class RowsModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def roleNames(self):
        return {Qt.ItemDataRole.UserRole + 1: QByteArray(b"row")}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and 0 <= index.row() < len(self.rows):
            if role == Qt.ItemDataRole.UserRole + 1:
                return self.rows[index.row()]
        return None

    def replace(self, rows):
        rows = list(rows)
        if rows == self.rows:
            return
        identities = [row.get("id") for row in rows]
        if identities and None not in identities and identities == [row.get("id") for row in self.rows]:
            previous, self.rows = self.rows, rows
            for index, (old, new) in enumerate(zip(previous, rows)):
                if old != new:
                    self.dataChanged.emit(self.index(index), self.index(index), [Qt.ItemDataRole.UserRole + 1])
            return
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    @Slot(int, result="QVariantMap")
    def get(self, index):
        return self.rows[index] if 0 <= index < len(self.rows) else {}
