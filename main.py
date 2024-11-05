import sys
import os
import subprocess
import platform
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QPushButton, QComboBox, QMessageBox
)
from PyQt6.QtGui import QPixmap, QFont, QMovie, QIcon
from PyQt6.QtCore import Qt


class USBWriteBlocker(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("USB Write Blocker")
        self.setGeometry(50,50,100,80)

        self.setWindowIcon(QIcon('icon.png'))  

        main_layout = QVBoxLayout()

        # 1. Display the logo centered
        self.logo_label = QLabel(self)
        pixmap = QPixmap('logo.png')  # Replace with the path to your logo
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setFixedSize(200, 100)  # Set fixed size for the logo
        self.logo_label.setScaledContents(True)  # Ensure the image scales to fit
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.logo_label)

        # 2. Add the "Update" button with a GIF
        self.update_button = QPushButton("Update USB List", self)
        self.update_button.clicked.connect(self.refresh_usb_devices)

        main_layout.addWidget(self.update_button)


        # 3. USB Selection combo box
        self.usb_combo = QComboBox(self)
        self.refresh_usb_devices()
        main_layout.addWidget(self.usb_combo)

        # 4. Start Blocking Button
        self.block_button = QPushButton("Start to Block Write", self)
        self.block_button.clicked.connect(self.block_write)
        main_layout.addWidget(self.block_button)

        # 5. Status image (this will show the GIF if the operation succeeds)
        self.status_label = QLabel(self)
        self.status_label.setFixedSize(300, 281)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()  # Hide initially
        main_layout.addWidget(self.status_label)

        # 6. Stop WriteBlocker Button (Hidden initially)
        self.stop_button = QPushButton("Stop WriteBlocker", self)
        self.stop_button.clicked.connect(self.stop_write_blocker)
        # Make the button red
        self.stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.stop_button.hide()  # Hide initially
        main_layout.addWidget(self.stop_button)

        # 7. Copyright information
        self.copyright_label = QLabel("©2024 Ahmed Alghamdi - https://github.com/ahmed0or1")
        self.copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        self.copyright_label.setFont(font)
        main_layout.addWidget(self.copyright_label)

        # Set main layout to a central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def refresh_usb_devices(self):
        # Clear the current items in the combo box
        self.usb_combo.clear()

        # Detect USB devices based on the operating system
        if platform.system() == 'Linux':
            usb_devices = self.get_usb_devices_linux()
        elif platform.system() == 'Windows':
            usb_devices = self.get_usb_devices_windows()
        else:
            usb_devices = []

        if not usb_devices:
            self.usb_combo.addItem("No USB devices connected")
        else:
            self.usb_combo.addItems(usb_devices)

    def get_usb_devices_linux(self):
        usb_devices = []
        result = subprocess.run(['lsblk', '-o', 'NAME,MOUNTPOINT'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "/media" in line or "/mnt" in line:
                device = line.split()[0]
                usb_devices.append(f"/dev/{device}")
        return usb_devices

    def get_usb_devices_windows(self):
        usb_devices = []
        # Get logical disks that are removable (USB)
        result = subprocess.run(['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'DeviceID,VolumeName'],
                                capture_output=True, text=True)
        devices = result.stdout.splitlines()

        # Get physical devices for USB (this will include the device name)
        physical_result = subprocess.run(
            ['wmic', 'diskdrive', 'where', 'MediaType="Removable Media"', 'get', 'DeviceID,Model'], capture_output=True,
            text=True)
        physical_devices = physical_result.stdout.splitlines()

        device_info = {}
        for line in physical_devices:
            if line.startswith("DeviceID") or line.strip() == "":
                continue
            parts = line.split()
            device_id = parts[0].strip()  # Physical device ID
            device_name = " ".join(parts[1:]).strip()  # Device name (model)
            device_info[device_id] = device_name

        for line in devices:
            if line.startswith("DeviceID") or line.strip() == "":
                continue
            parts = line.split()
            partition = parts[0]  # Logical drive (partition)
            volume_name = parts[1] if len(parts) > 1 else ""  # Volume name if available
            for device_id, device_name in device_info.items():
                usb_devices.append(f"{device_name} ({partition} - {volume_name})")

        return usb_devices

    def block_write(self):
        selected_usb = self.usb_combo.currentText()
        if "No USB devices" in selected_usb:
            QMessageBox.warning(self, "Error", "No USB device selected")
            return

        # Block write access based on the operating system
        if platform.system() == 'Linux':
            success = self.block_write_linux(selected_usb)
        elif platform.system() == 'Windows':
            success = self.block_write_windows(selected_usb)
        else:
            success = False

        # Show a success GIF if the operation worked
        if success:
            movie = QMovie('usb.gif')  # Replace with your 'usb.gif' path
            self.status_label.setMovie(movie)
            self.status_label.show()
            movie.start()
            self.stop_button.show()  # Show the stop button after starting
            self.block_button.hide()  # Hide the start button
            self.setGeometry(50, 50, 100, 200)

        else:
            QMessageBox.critical(self, "Error", "Failed to block write access")

    def stop_write_blocker(self):
        try:
            # Extract the drive letter using a regular expression
            selected_usb = self.usb_combo.currentText()
            match = re.search(r'\((\w):', selected_usb)
            if not match:
                QMessageBox.critical(self, "Error", "Invalid USB device selection")
                return False

            drive_letter = match.group(1)  # Extracts the drive letter, e.g., 'D'

            # Create the diskpart script to remove readonly attribute
            script = f"""
            select volume {drive_letter}
            attributes disk clear readonly
            """
            with open('diskpart_script.txt', 'w') as f:
                f.write(script)

            # Run the diskpart command with the script
            result = subprocess.run(['diskpart', '/s', 'diskpart_script.txt'], capture_output=True, text=True,
                                    shell=True)

            if result.returncode != 0:
                print(f"Error: {result.stderr}")
                print(f"Command output: {result.stdout}")
                QMessageBox.critical(self, "Error", "Failed to stop WriteBlocker")
                return False
            else:
                print(f"Success: {result.stdout}")
                os.remove('diskpart_script.txt')

                # Stop the movie and hide the status label and stop button
                self.status_label.hide()
                self.stop_button.hide()
                self.block_button.show()  # Show the start button again
                QMessageBox.information(self, "Stopped", "WriteBlocker has been stopped")
                return True

        except Exception as e:
            print(f"Error: {e}")
            QMessageBox.critical(self, "Error", "An error occurred while stopping WriteBlocker")
            return False

    def block_write_linux(self, selected_usb):
        try:
            subprocess.run(['sudo', 'mount', '-o', 'remount,ro', selected_usb], check=True)
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    def block_write_windows(self, selected_usb):
        try:
            # Extract the drive letter using a regular expression
            match = re.search(r'\((\w):', selected_usb)
            if not match:
                QMessageBox.critical(self, "Error", "Invalid USB device selection")
                return False

            drive_letter = match.group(1)  # Extracts the drive letter, e.g., 'D'

            # Create the diskpart script to block write access
            script = f"""
            select volume {drive_letter}
            attributes disk set readonly
            """
            with open('diskpart_script.txt', 'a') as f:
                f.write(script)

            # Run the diskpart command with the script
            result = subprocess.run(['diskpart', '/s', 'diskpart_script.txt'], capture_output=True, text=True, shell=True)

            if result.returncode != 0:
                print(f"Error: {result.stderr}")
                print(f"Command output: {result.stdout}")
                return False
            else:
                print(f"Success: {result.stdout}")
                os.remove('diskpart_script.txt')
                return True

        except Exception as e:
            print(f"Error: {e}")
            return False

# Main application loop
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = USBWriteBlocker()
    window.show()
    sys.exit(app.exec())
