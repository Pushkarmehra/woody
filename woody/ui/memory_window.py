"""
Woody Memory Window — Visual Multi-Turn Task & Context Inspector.

A dedicated dark-glassmorphic PySide6 window displaying:
  1. Active Task & Dialogue Memory Window (recent requests, questions, answers, and resolutions)
  2. Semantic Profile & Stored Facts (user name, preferences, saved notes)
  3. Episodic Conversation History
  4. Live controls to search, filter, refresh, and clear the memory window.

Runnable standalone: python -m woody.ui.memory_window
Or triggered from Woody tray menu / voice command: 'open memory window'.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QTabWidget,
    QStyledItemDelegate, QStyleOptionViewItem, QApplication, QFrame,
)

from woody.utils.logging import get_logger

log = get_logger(__name__)

WINDOW_STORAGE_FILE = Path("~/.Woody/task_memory_window.json").expanduser()
PREFERENCES_FILE = Path("~/.Woody/preferences.json").expanduser()


class MemoryItemDelegate(QStyledItemDelegate):
    """Custom dark-glassmorphic delegate for memory window items."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Any) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(6, 4, -6, -4)
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 10, 10)

        # Card Background
        if option.state & 0x0001:  # Selected
            painter.fillPath(path, QBrush(QColor(99, 102, 241, 35)))
            painter.setPen(QColor(99, 102, 241, 120))
            painter.drawPath(path)
        else:
            painter.fillPath(path, QBrush(QColor(255, 255, 255, 10)))
            painter.setPen(QColor(255, 255, 255, 18))
            painter.drawPath(path)

        data = index.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        # Header / Title
        painter.setPen(QColor(255, 255, 255, 230))
        painter.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        title_rect = rect.adjusted(14, 8, -90, -32)
        title_text = data.get("title", "")
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, title_text)

        # Time / Status badge
        time_text = data.get("time", "")
        if time_text:
            painter.setPen(QColor(148, 163, 184))
            painter.setFont(QFont("Inter", 8))
            time_rect = rect.adjusted(rect.width() - 95, 8, -12, -32)
            painter.drawText(time_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, time_text)

        # Subtitle / Details
        painter.setPen(QColor(203, 213, 225, 190))
        painter.setFont(QFont("Inter", 9))
        detail_rect = rect.adjusted(14, 28, -14, -6)
        detail_text = data.get("detail", "")
        painter.drawText(detail_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, detail_text)

        painter.end()

    def sizeHint(self, option: QStyleOptionViewItem, index: Any) -> QSize:
        return QSize(0, 62)


class MemoryWindow(QWidget):
    """
    Sleek OLED glassmorphic window displaying live Task & Context memory.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Woody — Memory Window")
        self.setMinimumSize(600, 680)
        self.setStyleSheet("""
            QWidget {
                background: #0a0a12;
                color: #f8fafc;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: #0e0e18;
                border-radius: 12px;
                top: -1px;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.04);
                color: rgba(255, 255, 255, 0.65);
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #6366f1;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
            QLineEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 8px 14px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #6366f1;
                background: rgba(255, 255, 255, 0.08);
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 8px 16px;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(99, 102, 241, 0.3);
                border-color: #6366f1;
            }
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
        """)
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ── Header ────────────────────────────────────────────
        header_row = QHBoxLayout()

        icon_lbl = QLabel("🧠")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        header_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("Memory Window")
        title_lbl.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff;")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel("Multi-turn conversational context, active tasks & knowledge")
        sub_lbl.setFont(QFont("Inter", 9))
        sub_lbl.setStyleSheet("color: #94a3b8;")
        title_vbox.addWidget(sub_lbl)
        header_row.addLayout(title_vbox)

        header_row.addStretch()

        live_badge = QLabel("● Live Context")
        live_badge.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        live_badge.setStyleSheet("color: #34d399; background: rgba(52, 211, 153, 0.12); padding: 4px 10px; border-radius: 12px;")
        header_row.addWidget(live_badge)

        layout.addLayout(header_row)

        # ── Search & Filter ───────────────────────────────────
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search tasks, memories, or dialogue turns...")
        self._search.textChanged.connect(self._filter_items)
        search_row.addWidget(self._search)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        search_row.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear Window")
        clear_btn.setStyleSheet("QPushButton:hover { background: rgba(244, 63, 94, 0.3); border-color: #f43f5e; }")
        clear_btn.clicked.connect(self._clear_memory_window)
        search_row.addWidget(clear_btn)

        layout.addLayout(search_row)

        # ── Tabs ──────────────────────────────────────────────
        self._tabs = QTabWidget()

        # Tab 1: Active Task Memory Window
        self._task_list = QListWidget()
        self._task_list.setItemDelegate(MemoryItemDelegate())
        self._tabs.addTab(self._task_list, "🕒 Active Tasks & Turns")

        # Tab 2: Semantic Facts & Knowledge
        self._semantic_list = QListWidget()
        self._semantic_list.setItemDelegate(MemoryItemDelegate())
        self._tabs.addTab(self._semantic_list, "🧠 Stored Facts & Profile")

        # Tab 3: Calendar & Reminders Memory
        self._calendar_list = QListWidget()
        self._calendar_list.setItemDelegate(MemoryItemDelegate())
        self._tabs.addTab(self._calendar_list, "📅 Calendar & Reminders")

        layout.addWidget(self._tabs)

        # ── Footer Status ─────────────────────────────────────
        self._status_lbl = QLabel("Memory window active • 0 tasks loaded")
        self._status_lbl.setFont(QFont("Inter", 8))
        self._status_lbl.setStyleSheet("color: #64748b;")
        layout.addWidget(self._status_lbl)

    def refresh_data(self) -> None:
        """Load and display data from memory files."""
        self._task_list.clear()
        self._semantic_list.clear()
        self._calendar_list.clear()

        # 1. Load Task Window
        task_count = 0
        if WINDOW_STORAGE_FILE.exists():
            try:
                with open(WINDOW_STORAGE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    turns = data.get("turns", [])
                    for t in reversed(turns):
                        req = t.get("user_request", "Request")
                        agent = t.get("agent", "")
                        action = t.get("action", "")
                        status = t.get("status", "done")
                        time_str = t.get("time_str", "")
                        if time_str and len(time_str) > 11:
                            time_str = time_str[11:16]

                        item = QListWidgetItem(self._task_list)
                        item.setData(Qt.ItemDataRole.UserRole, {
                            "title": f"\"{req}\"",
                            "detail": f"→ {agent}.{action} [{status}]",
                            "time": time_str,
                            "raw": t,
                        })
                        task_count += 1
            except Exception as e:
                log.debug("memory_window.load_tasks_error", error=str(e))

        if task_count == 0:
            item = QListWidgetItem(self._task_list)
            item.setData(Qt.ItemDataRole.UserRole, {
                "title": "No active tasks in window yet",
                "detail": "Ask Woody to add a reminder, open an app, or analyze your screen!",
                "time": "Now",
            })

        # 2. Load Semantic Preferences & Facts
        fact_count = 0
        if PREFERENCES_FILE.exists():
            try:
                with open(PREFERENCES_FILE, encoding="utf-8") as f:
                    prefs = json.load(f)
                    name = prefs.get("name")
                    if name:
                        item = QListWidgetItem(self._semantic_list)
                        item.setData(Qt.ItemDataRole.UserRole, {
                            "title": f"User Name: {name}",
                            "detail": "Primary user identity recognized by Woody",
                            "time": "Profile",
                        })
                        fact_count += 1

                    for k, v in prefs.get("facts", {}).items():
                        item = QListWidgetItem(self._semantic_list)
                        item.setData(Qt.ItemDataRole.UserRole, {
                            "title": f"Fact: {k}",
                            "detail": f"{v}",
                            "time": "Fact",
                        })
                        fact_count += 1

                    for n in prefs.get("notes", []):
                        item = QListWidgetItem(self._semantic_list)
                        item.setData(Qt.ItemDataRole.UserRole, {
                            "title": f"Note: {n.get('text', '')}",
                            "detail": f"Saved at {n.get('timestamp', '')[:16]}",
                            "time": "Note",
                        })
                        fact_count += 1
            except Exception as e:
                log.debug("memory_window.load_facts_error", error=str(e))

        if fact_count == 0:
            item = QListWidgetItem(self._semantic_list)
            item.setData(Qt.ItemDataRole.UserRole, {
                "title": "No custom facts or notes stored",
                "detail": "Say 'remember that my name is Pushkar' or 'save note: ...'",
                "time": "Profile",
            })

        # 3. Load Calendar & Reminders
        cal_file = Path("~/.Woody/calendar_events.json").expanduser()
        cal_count = 0
        if cal_file.exists():
            try:
                with open(cal_file, encoding="utf-8") as f:
                    events = json.load(f)
                    for ev in reversed(events):
                        title = ev.get("title", "Event")
                        start = ev.get("start_time", "")
                        item = QListWidgetItem(self._calendar_list)
                        item.setData(Qt.ItemDataRole.UserRole, {
                            "title": f"📅 {title}",
                            "detail": f"Scheduled for {start}",
                            "time": "Calendar",
                        })
                        cal_count += 1
            except Exception:
                pass

        if cal_count == 0:
            item = QListWidgetItem(self._calendar_list)
            item.setData(Qt.ItemDataRole.UserRole, {
                "title": "No calendar events found",
                "detail": "Ask Woody to add a reminder or schedule an event!",
                "time": "Empty",
            })

        self._status_lbl.setText(f"Memory window active • {task_count} tasks • {fact_count} facts • {cal_count} calendar items")

    def _filter_items(self, query: str) -> None:
        """Filter list items by search query."""
        q = query.lower().strip()
        for lst in (self._task_list, self._semantic_list, self._calendar_list):
            for i in range(lst.count()):
                item = lst.item(i)
                data = item.data(Qt.ItemDataRole.UserRole) or {}
                match = not q or q in data.get("title", "").lower() or q in data.get("detail", "").lower()
                item.setHidden(not match)

    def _clear_memory_window(self) -> None:
        """Reset task memory window file."""
        if WINDOW_STORAGE_FILE.exists():
            try:
                with open(WINDOW_STORAGE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"turns": [], "pending_action": None, "pending_params": {}}, f)
            except Exception:
                pass
        self.refresh_data()


def show_memory_window() -> MemoryWindow:
    """Launch or show the MemoryWindow."""
    app = QApplication.instance()
    is_standalone = app is None
    if is_standalone:
        app = QApplication(sys.argv)

    win = MemoryWindow()
    win.show()

    if is_standalone:
        app.exec()
    return win


if __name__ == "__main__":
    show_memory_window()
