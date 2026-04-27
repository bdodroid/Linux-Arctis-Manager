from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from linux_arctis_manager.i18n import I18n


class QStatusWidget(QWidget):
    main_layout: QVBoxLayout

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)
    
    def clean_layout(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def update_status(self, new_status: dict[str, dict[str, dict[str, str|int]]]):
        if hasattr(self, 'status') and new_status == self.status:
            return

        # Check if user is currently dragging a slider to avoid jumping
        is_dragging = False
        if hasattr(self, 'main_layout'):
            for i in range(self.main_layout.count()):
                item = self.main_layout.itemAt(i)
                if item and item.layout():
                    for j in range(item.layout().count()):
                        w = item.layout().itemAt(j).widget()
                        from PySide6.QtWidgets import QSlider
                        if isinstance(w, QSlider) and w.isSliderDown():
                            is_dragging = True
                            break
        
        if is_dragging:
            return

        self.status = new_status
        self.clean_layout()
        # ... rest of the method logic follows ...
        if not self.status:
            label = QLabel(I18n.get_instance().translate('ui', 'no_device_detected'))
            label.font().setBold(True)
            self.main_layout.addWidget(label)
            return

        index = 0
        for category, status_obj in self.status.items():
            if index > 0:
                line_separator = QWidget()
                line_separator.setFixedHeight(2)
                self.main_layout.addWidget(line_separator)
            index += 1

            category_label = QLabel(I18n.get_instance().translate('status', category))
            category_font = category_label.font()
            category_font.setBold(True)
            category_font.setPointSize(16)
            category_label.setFont(category_font)
            self.main_layout.addWidget(category_label)

            if category == 'mixer' and 'media_mix' in status_obj and 'chat_mix' in status_obj:
                from PySide6.QtWidgets import QHBoxLayout, QSlider
                from linux_arctis_manager.gui.dbus_wrapper import DbusWrapper
                
                try:
                    media_val = int(status_obj['media_mix']['value'])
                    chat_val = int(status_obj['chat_mix']['value'])
                    
                    balance = 50
                    if media_val > chat_val:
                        balance = 50 - (media_val - chat_val) // 2
                    elif chat_val > media_val:
                        balance = 50 + (chat_val - media_val) // 2
                    
                    row_layout = QHBoxLayout()
                    row_layout.addWidget(QLabel("Media"))
                    slider = QSlider(Qt.Orientation.Horizontal)
                    slider.setRange(0, 100)
                    slider.setValue(balance)
                    slider.valueChanged.connect(DbusWrapper.change_mixer_balance)
                    row_layout.addWidget(slider)
                    row_layout.addWidget(QLabel("Chat"))
                    self.main_layout.addLayout(row_layout)
                    continue
                except (ValueError, KeyError, TypeError):
                    pass

            for status, status_o in status_obj.items():
                if status_o['type'] == 'percentage':
                    from PySide6.QtWidgets import QProgressBar, QHBoxLayout
                    
                    row_layout = QHBoxLayout()
                    label = QLabel(f"{I18n.translate('status', status)}: ")
                    progress = QProgressBar()
                    progress.setRange(0, 100)
                    
                    try:
                        val = int(float(status_o['value']))
                        progress.setValue(val)
                    except (ValueError, TypeError):
                        progress.setValue(0)
                        
                    progress.setTextVisible(True)
                    progress.setFormat("%p%")
                    
                    row_layout.addWidget(label)
                    row_layout.addWidget(progress)
                    self.main_layout.addLayout(row_layout)
                else:
                    label = QLabel(
                        f"{I18n.translate('status', status)}: "
                        f"{I18n.translate('status_values', status_o['value'])}"
                    )
                    self.main_layout.addWidget(label)
