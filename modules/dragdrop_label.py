# -*- coding: utf-8 -*-
import os
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *


class DragDropLabel(QLabel):
    file_dropped = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_vars()
        self.set_widget()
        
    def set_vars(self):
        self._original_pixmap = None
        
    def set_widget(self):
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Drop Image File Here")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.default_style = self.get_style()
        self.highlight_style = self.get_highlight_style()
        self.setStyleSheet(self.default_style)
        
    def get_style(self):
        return """
        QLabel {
            background-color: rgb(35, 35, 35);
            color: rgb(60, 60, 60);
            font-family: "Lato Black";
            font-size: 20px;
            border: 2px dashed rgb(60, 60, 60);
            border-radius: 4px;
        }
        """
    
    def get_highlight_style(self):
        return """
        QLabel {
            background-color: rgb(45, 45, 45);
            color: rgb(79, 210, 170);
            font-family: "Lato Black";
            font-size: 20px;
            border: 2px dashed rgb(59, 190, 150);
            border-radius: 4px;
        }
        """
    
    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
            
        file_paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if len(file_paths) != 1:
            event.ignore()
            return
        file_path = file_paths[0]
        
        self.setText(os.path.basename(file_path))
        event.acceptProposedAction()
        self.setStyleSheet(self.highlight_style)
    
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
    
    def dragLeaveEvent(self, event):
        self.setText("Drop Scene File Here")
        self.setStyleSheet(self.default_style)
    
    def dropEvent(self, event):
        self.setText("Drop Scene File Here")
        self.setStyleSheet(self.default_style)
        
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        file_paths = [url.toLocalFile() for url in event.mimeData().urls()]
        
        if len(file_paths) != 1:
            QMessageBox.warning(self, "Invalid Drop", "You can only drop one file at a time.")
            return
        
        file_path = file_paths[0]
        
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self._original_pixmap = pixmap
            scaled = self._original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
        else:
            self._original_pixmap = None
            self.clear()
        
        self.file_dropped.emit(file_path)
        
        event.acceptProposedAction()
        
    def resizeEvent(self, event):
        # adjust pixmap size from original if available
        if self._original_pixmap:
            scaled = self._original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
        else:
            super().resizeEvent(event)