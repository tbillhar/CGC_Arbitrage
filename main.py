"""PySide6 desktop app for scanning CGC slab arbitrage candidates."""

from __future__ import annotations

import csv
import sys
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, PRESET_WATCHLIST_PATH, PRICING
from database import CandidateListing, Database, WatchlistItem
from ebay_client import EbayClient
from gocollect_client import GoCollectClient
from parser import parse_listing_title
from valuation import FairValue, LocalFairValueProvider, calculate_deal


class MoneyItem(QTableWidgetItem):
    def __init__(self, value: float) -> None:
        super().__init__(f"${value:,.2f}")
        self.setData(Qt.ItemDataRole.UserRole, value)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        return float(self.data(Qt.ItemDataRole.UserRole) or 0) < float(
            other.data(Qt.ItemDataRole.UserRole) or 0
        )


class PercentItem(QTableWidgetItem):
    def __init__(self, value: float) -> None:
        super().__init__(f"{value * 100:.1f}%")
        self.setData(Qt.ItemDataRole.UserRole, value)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        return float(self.data(Qt.ItemDataRole.UserRole) or 0) < float(
            other.data(Qt.ItemDataRole.UserRole) or 0
        )


class ScannerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.database = Database()
        self.ebay = EbayClient()
        self.gocollect = GoCollectClient()
        self.local_values = LocalFairValueProvider()
        self.url_by_row: dict[int, str] = {}

        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self._build_ui()
        self._load_watchlist()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        form = QFormLayout()
        self.title_input = QLineEdit()
        self.issue_input = QLineEdit()
        self.min_grade_input = QDoubleSpinBox()
        self.min_grade_input.setRange(0.5, 10.0)
        self.min_grade_input.setSingleStep(0.1)
        self.min_grade_input.setValue(9.0)
        self.max_grade_input = QDoubleSpinBox()
        self.max_grade_input.setRange(0.5, 10.0)
        self.max_grade_input.setSingleStep(0.1)
        self.max_grade_input.setValue(9.8)
        self.margin_input = QSpinBox()
        self.margin_input.setRange(0, 95)
        self.margin_input.setValue(int(PRICING.default_profit_margin * 100))

        form.addRow("Title", self.title_input)
        form.addRow("Issue number", self.issue_input)
        form.addRow("Minimum grade", self.min_grade_input)
        form.addRow("Maximum grade", self.max_grade_input)
        form.addRow("Target profit margin %", self.margin_input)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        add_button = QPushButton("Add to watchlist")
        import_button = QPushButton("Load liquid list")
        delete_button = QPushButton("Remove selected")
        scan_button = QPushButton("Scan watchlist")
        add_button.clicked.connect(self._add_watchlist_item)
        import_button.clicked.connect(self._import_preset_watchlist)
        delete_button.clicked.connect(self._delete_selected_watchlist_item)
        scan_button.clicked.connect(self._scan_watchlist)
        button_row.addWidget(add_button)
        button_row.addWidget(import_button)
        button_row.addWidget(delete_button)
        button_row.addStretch(1)
        button_row.addWidget(scan_button)
        layout.addLayout(button_row)

        layout.addWidget(QLabel("Watchlist"))
        self.watchlist_table = QTableWidget(0, 5)
        self.watchlist_table.setHorizontalHeaderLabels(["Title", "Issue", "Min Grade", "Max Grade", "Margin"])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.watchlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.watchlist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.watchlist_table, 1)

        layout.addWidget(QLabel("Candidate listings"))
        self.results_table = QTableWidget(0, 10)
        self.results_table.setHorizontalHeaderLabels(
            [
                "Title",
                "Issue",
                "Grade",
                "Pages",
                "Fair Value",
                "Price",
                "Max Buy",
                "Profit",
                "Margin",
                "URL",
            ]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.cellDoubleClicked.connect(self._open_listing)
        layout.addWidget(self.results_table, 2)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)

    def _add_watchlist_item(self) -> None:
        title = self.title_input.text().strip()
        issue = self.issue_input.text().strip()
        if not title or not issue:
            QMessageBox.warning(self, APP_NAME, "Title and issue number are required.")
            return
        if self.min_grade_input.value() > self.max_grade_input.value():
            QMessageBox.warning(self, APP_NAME, "Minimum grade cannot be higher than maximum grade.")
            return

        self.database.add_watchlist_item(
            WatchlistItem(
                id=None,
                title=title,
                issue_number=issue,
                min_grade=self.min_grade_input.value(),
                max_grade=self.max_grade_input.value(),
                target_profit_margin=self.margin_input.value() / 100,
            )
        )
        self.title_input.clear()
        self.issue_input.clear()
        self._load_watchlist()

    def _import_preset_watchlist(self) -> None:
        if not PRESET_WATCHLIST_PATH.exists():
            QMessageBox.warning(self, APP_NAME, f"Preset list not found: {PRESET_WATCHLIST_PATH}")
            return

        try:
            items = self._read_preset_watchlist()
        except ValueError as error:
            QMessageBox.warning(self, APP_NAME, str(error))
            return

        imported_count = self.database.add_watchlist_items(items)
        self._load_watchlist()
        self.status_label.setText(
            f"Imported {imported_count} liquid list rows. {len(items) - imported_count} duplicates skipped."
        )

    def _read_preset_watchlist(self) -> list[WatchlistItem]:
        required_columns = {"title", "issue_number", "min_grade", "max_grade", "target_profit_margin"}
        with PRESET_WATCHLIST_PATH.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
                missing = ", ".join(sorted(required_columns - set(reader.fieldnames or [])))
                raise ValueError(f"Preset list is missing required columns: {missing}")

            items: list[WatchlistItem] = []
            for line_number, row in enumerate(reader, start=2):
                title = (row.get("title") or "").strip()
                issue_number = (row.get("issue_number") or "").strip()
                if not title or not issue_number:
                    raise ValueError(f"Preset list row {line_number} must include title and issue_number.")
                try:
                    min_grade = float(row["min_grade"])
                    max_grade = float(row["max_grade"])
                    target_profit_margin = float(row["target_profit_margin"])
                except (TypeError, ValueError) as error:
                    raise ValueError(f"Preset list row {line_number} contains invalid numeric values.") from error
                if min_grade > max_grade:
                    raise ValueError(f"Preset list row {line_number} has min_grade above max_grade.")

                items.append(
                    WatchlistItem(
                        id=None,
                        title=title,
                        issue_number=issue_number,
                        min_grade=min_grade,
                        max_grade=max_grade,
                        target_profit_margin=target_profit_margin,
                    )
                )
        return items

    def _delete_selected_watchlist_item(self) -> None:
        selected = self.watchlist_table.selectionModel().selectedRows()
        if not selected:
            return
        item_id = int(self.watchlist_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole))
        self.database.delete_watchlist_item(item_id)
        self._load_watchlist()

    def _load_watchlist(self) -> None:
        self.watchlist_table.setRowCount(0)
        for row_index, item in enumerate(self.database.get_watchlist()):
            self.watchlist_table.insertRow(row_index)
            values: list[Any] = [
                item.title,
                item.issue_number,
                f"{item.min_grade:g}",
                f"{item.max_grade:g}",
                f"{item.target_profit_margin * 100:.0f}%",
            ]
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                if column == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, item.id)
                self.watchlist_table.setItem(row_index, column, table_item)

    def _scan_watchlist(self) -> None:
        watchlist = self.database.get_watchlist()
        if not watchlist:
            QMessageBox.information(self, APP_NAME, "Add at least one watchlist item before scanning.")
            return

        candidates: list[CandidateListing] = []
        for item in watchlist:
            self.status_label.setText(f"Scanning {item.title} #{item.issue_number}...")
            QApplication.processEvents()
            listings = self.ebay.search_active_listings(
                item.title,
                item.issue_number,
                item.min_grade,
                item.max_grade,
            )
            for listing in listings:
                parsed = parse_listing_title(listing.title)
                if parsed.grade is None or not (item.min_grade <= parsed.grade <= item.max_grade):
                    continue
                fair_value = self._fetch_fair_value(item.title, item.issue_number, parsed.grade)
                if fair_value is None:
                    continue
                deal = calculate_deal(fair_value.value, listing.price, item.target_profit_margin)
                if not deal.is_candidate:
                    continue
                candidates.append(
                    CandidateListing(
                        title=listing.title,
                        issue_number=parsed.issue_number or item.issue_number,
                        grade=parsed.grade,
                        page_quality=parsed.page_quality,
                        fair_value=fair_value.value,
                        listing_price=listing.price,
                        max_buy_price=deal.max_buy_price,
                        estimated_profit=deal.estimated_profit,
                        estimated_margin=deal.estimated_margin,
                        url=listing.item_url,
                        source_item_id=listing.item_id,
                    )
                )

        self.database.replace_scan_results(candidates)
        self._render_candidates(candidates)
        self.status_label.setText(f"Scan complete. {len(candidates)} candidates found.")

    def _fetch_fair_value(self, title: str, issue_number: str, grade: float) -> FairValue | None:
        fair_value = self.gocollect.fetch_fair_value(title, issue_number, grade)
        if fair_value is not None:
            return fair_value

        try:
            return self.local_values.fetch_fair_value(title, issue_number, grade)
        except ValueError as error:
            QMessageBox.warning(self, APP_NAME, str(error))
            return None

    def _render_candidates(self, candidates: list[CandidateListing]) -> None:
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        self.url_by_row.clear()
        for row_index, candidate in enumerate(candidates):
            self.results_table.insertRow(row_index)
            self.url_by_row[row_index] = candidate.url
            values: list[QTableWidgetItem] = [
                QTableWidgetItem(candidate.title),
                QTableWidgetItem(candidate.issue_number),
                QTableWidgetItem(f"{candidate.grade:g}" if candidate.grade is not None else ""),
                QTableWidgetItem(candidate.page_quality or ""),
                MoneyItem(candidate.fair_value),
                MoneyItem(candidate.listing_price),
                MoneyItem(candidate.max_buy_price),
                MoneyItem(candidate.estimated_profit),
                PercentItem(candidate.estimated_margin),
                QTableWidgetItem(candidate.url),
            ]
            for column, table_item in enumerate(values):
                self.results_table.setItem(row_index, column, table_item)
        self.results_table.setSortingEnabled(True)

    def _open_listing(self, row: int, _column: int) -> None:
        url_item = self.results_table.item(row, 9)
        if url_item and url_item.text():
            QDesktopServices.openUrl(QUrl(url_item.text()))

    def closeEvent(self, event: Any) -> None:
        self.database.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = ScannerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
