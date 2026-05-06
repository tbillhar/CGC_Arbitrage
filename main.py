"""PySide6 desktop app for scanning CGC slab arbitrage candidates."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, PRESET_WATCHLIST_PATH, PRICING, PricingConfig
from database import AppSettings, CandidateListing, Database, WatchlistItem
from ebay_client import EbayApiError, EbayAuthError, EbayClient, EbayCredentialsMissingError
from gocollect_client import GoCollectClient
from parser import DEAL_BREAKER_FLAGS, parse_listing_title
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


@dataclass
class ScanDiagnostics:
    watchlist_items: int = 0
    ebay_queries: int = 0
    listings_found: int = 0
    missing_price: int = 0
    not_slabbed: int = 0
    missing_grade: int = 0
    slabbed_missing_grade: int = 0
    issue_mismatch: int = 0
    deal_breaker_flags: int = 0
    grade_out_of_range: int = 0
    missing_fair_value: int = 0
    unprofitable: int = 0
    candidates: int = 0
    selling_fee_rate: float = 0.0
    payment_fee_rate: float = 0.0
    shipping_cost: float = 0.0
    default_profit_margin: float = 0.0
    api_errors: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"Watchlist rows scanned: {self.watchlist_items}",
            f"eBay searches attempted: {self.ebay_queries}",
            f"eBay listings returned: {self.listings_found}",
            f"Skipped: no usable price: {self.missing_price}",
            f"Skipped: not slabbed: {self.not_slabbed}",
            f"Skipped: no parsed CGC grade: {self.missing_grade}",
            f"Skipped: slabbed but no parsed grade: {self.slabbed_missing_grade}",
            f"Skipped: issue mismatch: {self.issue_mismatch}",
            f"Skipped: qualified/restored/incomplete: {self.deal_breaker_flags}",
            f"Skipped: grade outside watchlist range: {self.grade_out_of_range}",
            f"Skipped: no GoCollect/local fair value: {self.missing_fair_value}",
            f"Skipped: below target profit: {self.unprofitable}",
            f"Candidates shown: {self.candidates}",
            (
                "Assumptions: "
                f"selling fee {self.selling_fee_rate * 100:.2f}%, "
                f"payment fee {self.payment_fee_rate * 100:.2f}%, "
                f"shipping ${self.shipping_cost:.2f}, "
                f"default margin {self.default_profit_margin * 100:.1f}%"
            ),
        ]
        if self.api_errors:
            lines.append("API/configuration issues:")
            lines.extend(f"- {error}" for error in self.api_errors)
        return "\n".join(lines)


class ScannerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.database = Database()
        self.ebay = EbayClient()
        self.gocollect = GoCollectClient()
        self.local_values = LocalFairValueProvider()
        self.url_by_row: dict[int, str] = {}
        self.current_candidates: list[CandidateListing] = []

        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self._build_ui()
        self._load_scan_settings()
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

        settings_group = QGroupBox("Scan settings")
        settings_form = QFormLayout(settings_group)
        self.selling_fee_input = QDoubleSpinBox()
        self.selling_fee_input.setRange(0, 50)
        self.selling_fee_input.setSingleStep(0.25)
        self.selling_fee_input.setDecimals(2)
        self.selling_fee_input.setSuffix("%")
        self.selling_fee_input.setValue(PRICING.selling_fee_rate * 100)
        self.payment_fee_input = QDoubleSpinBox()
        self.payment_fee_input.setRange(0, 20)
        self.payment_fee_input.setSingleStep(0.25)
        self.payment_fee_input.setDecimals(2)
        self.payment_fee_input.setSuffix("%")
        self.payment_fee_input.setValue(PRICING.payment_fee_rate * 100)
        self.shipping_cost_input = QDoubleSpinBox()
        self.shipping_cost_input.setRange(0, 500)
        self.shipping_cost_input.setSingleStep(1)
        self.shipping_cost_input.setDecimals(2)
        self.shipping_cost_input.setPrefix("$")
        self.shipping_cost_input.setValue(PRICING.shipping_cost)
        self.default_margin_input = QDoubleSpinBox()
        self.default_margin_input.setRange(0, 95)
        self.default_margin_input.setSingleStep(1)
        self.default_margin_input.setDecimals(1)
        self.default_margin_input.setSuffix("%")
        self.default_margin_input.setValue(PRICING.default_profit_margin * 100)
        self.default_margin_input.valueChanged.connect(self._sync_default_margin)

        settings_form.addRow("Selling fee", self.selling_fee_input)
        settings_form.addRow("Payment fee", self.payment_fee_input)
        settings_form.addRow("Shipping cost", self.shipping_cost_input)
        settings_form.addRow("Default margin", self.default_margin_input)
        layout.addWidget(settings_group)

        button_row = QHBoxLayout()
        add_button = QPushButton("Add to watchlist")
        import_button = QPushButton("Load liquid list")
        delete_button = QPushButton("Remove selected")
        scan_button = QPushButton("Scan watchlist")
        export_button = QPushButton("Export candidates CSV")
        add_button.clicked.connect(self._add_watchlist_item)
        import_button.clicked.connect(self._import_preset_watchlist)
        delete_button.clicked.connect(self._delete_selected_watchlist_item)
        scan_button.clicked.connect(self._scan_watchlist)
        export_button.clicked.connect(self._export_candidates)
        button_row.addWidget(add_button)
        button_row.addWidget(import_button)
        button_row.addWidget(delete_button)
        button_row.addStretch(1)
        button_row.addWidget(export_button)
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
        self.results_table = QTableWidget(0, 14)
        self.results_table.setHorizontalHeaderLabels(
            [
                "Title",
                "Issue",
                "Grade",
                "Pages",
                "Flags",
                "Fair Value",
                "Value Source",
                "Price",
                "Max Buy",
                "Profit",
                "Margin",
                "Seller",
                "Item ID",
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
        self.diagnostics_box = QPlainTextEdit()
        self.diagnostics_box.setReadOnly(True)
        self.diagnostics_box.setMaximumHeight(150)
        self.diagnostics_box.setPlainText("Scan diagnostics will appear here.")
        layout.addWidget(self.diagnostics_box)
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
        pricing = self._pricing_config()
        self._save_scan_settings()
        default_margin = self.default_margin_input.value() / 100
        diagnostics = ScanDiagnostics(
            watchlist_items=len(watchlist),
            selling_fee_rate=pricing.selling_fee_rate,
            payment_fee_rate=pricing.payment_fee_rate,
            shipping_cost=pricing.shipping_cost,
            default_profit_margin=default_margin,
        )
        for item in watchlist:
            self.status_label.setText(f"Scanning {item.title} #{item.issue_number}...")
            QApplication.processEvents()
            diagnostics.ebay_queries += 1
            try:
                listings = self.ebay.search_active_listings(
                    item.title,
                    item.issue_number,
                    item.min_grade,
                    item.max_grade,
                )
            except EbayCredentialsMissingError as error:
                diagnostics.api_errors.append(str(error))
                break
            except EbayAuthError as error:
                diagnostics.api_errors.append(str(error))
                break
            except EbayApiError as error:
                diagnostics.api_errors.append(f"{item.title} #{item.issue_number}: {error}")
                continue

            diagnostics.listings_found += len(listings)
            for listing in listings:
                if listing.price <= 0:
                    diagnostics.missing_price += 1
                    continue
                parsed = parse_listing_title(listing.title)
                if parsed.issue_number and not self._issue_matches(item.issue_number, parsed.issue_number):
                    diagnostics.issue_mismatch += 1
                    continue
                if parsed.grade is None:
                    if parsed.is_slabbed:
                        diagnostics.slabbed_missing_grade += 1
                    else:
                        diagnostics.not_slabbed += 1
                    diagnostics.missing_grade += 1
                    continue
                if DEAL_BREAKER_FLAGS.intersection(parsed.flags):
                    diagnostics.deal_breaker_flags += 1
                    continue
                if not (item.min_grade <= parsed.grade <= item.max_grade):
                    diagnostics.grade_out_of_range += 1
                    continue
                fair_value = self._fetch_fair_value(item.title, item.issue_number, parsed.grade)
                if fair_value is None:
                    diagnostics.missing_fair_value += 1
                    continue
                target_margin = item.target_profit_margin if item.target_profit_margin > 0 else default_margin
                deal = calculate_deal(fair_value.value, listing.price, target_margin, pricing)
                if not deal.is_candidate:
                    diagnostics.unprofitable += 1
                    continue
                candidates.append(
                    CandidateListing(
                        title=listing.title,
                        issue_number=parsed.issue_number or item.issue_number,
                        grade=parsed.grade,
                        page_quality=parsed.page_quality,
                        listing_flags=", ".join(parsed.flags),
                        fair_value=fair_value.value,
                        fair_value_source=fair_value.source,
                        listing_price=listing.price,
                        max_buy_price=deal.max_buy_price,
                        estimated_profit=deal.estimated_profit,
                        estimated_margin=deal.estimated_margin,
                        url=listing.item_url,
                        source_item_id=listing.item_id,
                        seller_username=listing.seller_username,
                    )
                )

        diagnostics.candidates = len(candidates)
        self.current_candidates = candidates
        self.database.replace_scan_results(candidates)
        self._render_candidates(candidates)
        self.diagnostics_box.setPlainText(diagnostics.to_text())
        if diagnostics.api_errors:
            self.status_label.setText("Scan stopped with configuration/API issues.")
        else:
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

    def _pricing_config(self) -> PricingConfig:
        return PricingConfig(
            selling_fee_rate=self.selling_fee_input.value() / 100,
            payment_fee_rate=self.payment_fee_input.value() / 100,
            shipping_cost=self.shipping_cost_input.value(),
            default_profit_margin=self.default_margin_input.value() / 100,
        )

    def _load_scan_settings(self) -> None:
        settings = self.database.get_app_settings()
        self.selling_fee_input.setValue(self._setting_float(settings, "selling_fee_rate", PRICING.selling_fee_rate) * 100)
        self.payment_fee_input.setValue(self._setting_float(settings, "payment_fee_rate", PRICING.payment_fee_rate) * 100)
        self.shipping_cost_input.setValue(self._setting_float(settings, "shipping_cost", PRICING.shipping_cost))
        self.default_margin_input.setValue(
            self._setting_float(settings, "default_profit_margin", PRICING.default_profit_margin) * 100
        )

    def _save_scan_settings(self) -> None:
        self.database.save_app_settings(
            AppSettings(
                selling_fee_rate=self.selling_fee_input.value() / 100,
                payment_fee_rate=self.payment_fee_input.value() / 100,
                shipping_cost=self.shipping_cost_input.value(),
                default_profit_margin=self.default_margin_input.value() / 100,
            )
        )

    def _setting_float(self, settings: dict[str, str], key: str, default: float) -> float:
        try:
            return float(settings.get(key, default))
        except (TypeError, ValueError):
            return default

    def _issue_matches(self, watch_issue: str, parsed_issue: str) -> bool:
        return self._normalize_issue(watch_issue) == self._normalize_issue(parsed_issue)

    def _normalize_issue(self, issue_number: str) -> str:
        return issue_number.strip().casefold().replace("#", "").replace(" ", "")

    def _sync_default_margin(self, value: float) -> None:
        if not self.margin_input.hasFocus():
            self.margin_input.setValue(round(value))

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
                QTableWidgetItem(candidate.listing_flags),
                MoneyItem(candidate.fair_value),
                QTableWidgetItem(candidate.fair_value_source),
                MoneyItem(candidate.listing_price),
                MoneyItem(candidate.max_buy_price),
                MoneyItem(candidate.estimated_profit),
                PercentItem(candidate.estimated_margin),
                QTableWidgetItem(candidate.seller_username),
                QTableWidgetItem(candidate.source_item_id),
                QTableWidgetItem(candidate.url),
            ]
            for column, table_item in enumerate(values):
                self.results_table.setItem(row_index, column, table_item)
        self.results_table.setSortingEnabled(True)

    def _open_listing(self, row: int, _column: int) -> None:
        url_item = self.results_table.item(row, 13)
        if url_item and url_item.text():
            QDesktopServices.openUrl(QUrl(url_item.text()))

    def _export_candidates(self) -> None:
        if not self.current_candidates:
            QMessageBox.information(self, APP_NAME, "There are no candidates to export.")
            return

        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export candidates",
            "cgc_candidates.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "title",
                    "issue_number",
                    "grade",
                    "page_quality",
                    "listing_flags",
                    "fair_value",
                    "fair_value_source",
                    "listing_price",
                    "max_buy_price",
                    "estimated_profit",
                    "estimated_margin",
                    "seller_username",
                    "source_item_id",
                    "url",
                ],
            )
            writer.writeheader()
            for candidate in self.current_candidates:
                writer.writerow(
                    {
                        "title": candidate.title,
                        "issue_number": candidate.issue_number,
                        "grade": candidate.grade,
                        "page_quality": candidate.page_quality,
                        "listing_flags": candidate.listing_flags,
                        "fair_value": candidate.fair_value,
                        "fair_value_source": candidate.fair_value_source,
                        "listing_price": candidate.listing_price,
                        "max_buy_price": candidate.max_buy_price,
                        "estimated_profit": candidate.estimated_profit,
                        "estimated_margin": candidate.estimated_margin,
                        "seller_username": candidate.seller_username,
                        "source_item_id": candidate.source_item_id,
                        "url": candidate.url,
                    }
                )
        self.status_label.setText(f"Exported {len(self.current_candidates)} candidates to {path}.")

    def closeEvent(self, event: Any) -> None:
        self._save_scan_settings()
        self.database.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = ScannerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
