import sys
import socket
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, \
    QHBoxLayout, QWidget, QComboBox
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import cx_Oracle
import time
import bluetooth

cx_Oracle.init_oracle_client(lib_dir=r"C:\instantclient_21_9")
cx_Oracle.clientversion()


class ScannerSimulator:
    def __init__(self, scanner_address, station_id, log_display):
        self.scanner_address = scanner_address
        self.station_id = station_id
        self.parameters = []
        self.num_parameters = 2
        self.exit_flag = False
        self.sock = None
        self.log_display = log_display
        self.thread = threading.Thread(target=self.read_socket, daemon=True)

    def connect(self):
        port = 1
        try:
            self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.sock.connect((self.scanner_address, port))
            self.log_display.append(f"Connected to scanner at {self.scanner_address}\n")
        except Exception as e:
            self.log_display.append(f"Failed to connect to scanner: {e}\n")
            self.stop()

    def read_socket(self):
        try:
            while not self.exit_flag:
                data = self.sock.recv(1024).decode('utf-8').strip()
                if not data:
                    continue
                self.process_line(data)
        except Exception as e:
            self.log_display.append(f"Error in socket communication: {e}\n")

    def process_line(self, line):
        if line.strip():
            self.parameters.append(line.strip())
            if len(self.parameters) == self.num_parameters:
                self.call_procedure(self.parameters[0], self.parameters[1])
                self.parameters = []

    def call_procedure(self, param1, param2):
        try:
            self.log_display.append(f"Calling procedure with parameters: {param1}, {param2}, {self.station_id}\n")
            # Connect to Oracle database
            username = 'USERNAME'
            password = 'PASSWORD'
            hostname = 'HOSTNAME'
            port = 1521
            service_name = 'SRVCNAME'
            dsn = cx_Oracle.makedsn(hostname, port, service_name=service_name)
            connection = cx_Oracle.connect(username, password, dsn)

            cursor = connection.cursor()

            plsql_block = """
            declare
                lv_y_n varchar2(100);
                lv_error_msg varchar2(100);
            begin
                CNL_SYS."CNL_FS_PCK".comp_sort( 
                    p_wms_unit_id_i       => :param1,
                    p_mht_pal_id_i        => :param2,
                    p_mht_station_id_i    => :station_id,
                    p_ok_yn_o             => :lv_y_n,
                    p_err_message_o       => :lv_error_msg
                );
            end;
            """

            # Ensure param1 and param2 are strings
            param1 = str(param1)
            param2 = str(param2)
            station_id = str(self.station_id)

            # Bind variables for output parameters
            lv_y_n = cursor.var(cx_Oracle.STRING)
            lv_error_msg = cursor.var(cx_Oracle.STRING)

            # Execute PL/SQL block with bind variables
            cursor.execute(plsql_block, param1=param1, param2=param2, station_id=station_id, lv_y_n=lv_y_n,
                           lv_error_msg=lv_error_msg)

            # output params
            outcome = lv_y_n.getvalue()
            error_msg = lv_error_msg.getvalue()

            self.log_display.append(f"lv_y_n: {outcome}\n")
            self.log_display.append(f"lv_error_msg: {error_msg}\n")

            connection.commit()

            cursor.close()
            connection.close()

            # Control LEDs color flow
            if outcome == 'Y':
                self.send_led_command('green')
                self.send_led_command('green')
                self.send_led_command('green')
            else:
                self.send_led_command('red')
                self.send_led_command('red')
                self.send_led_command('red')

        except Exception as e:
            self.log_display.append(f"Error executing SQL procedure: {e}\n")

    def send_led_command(self, command):
        try:
            if command == 'green':
                self.sock.send(b'\x63')  # Send 'c' for Green LED
                self.log_display.append("LED command c (green) sent successfully.\n")
            elif command == 'red':
                self.sock.send(b'\x62')  # Send 'b' for Red LED
                self.log_display.append("LED command b (red) sent successfully.\n")
            time.sleep(0.5)  # Short delay between blinks
        except Exception as e:
            self.log_display.append(f"Failed to send LED command: {e}\n")

    def start(self):
        self.connect()
        self.thread.start()

    def stop(self):
        self.exit_flag = True
        if self.sock:
            self.sock.close()
        self.log_display.append("Rhenus Wireless Scanner Application stopped.\n")


class DeviceDiscoveryThread(QThread):
    devices_discovered = pyqtSignal(list)

    def run(self):
        connected_devices = []
        nearby_devices = bluetooth.discover_devices(lookup_names=True)
        for addr, name in nearby_devices:
            if bluetooth.lookup_name(addr) is not None:
                connected_devices.append((addr, name))
        self.devices_discovered.emit(connected_devices)


class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.init_ui()
        self.scanner_simulator = None

    def init_ui(self):
        self.setWindowTitle("Rhenus Wireless Scanner Application")
        self.setGeometry(100, 100, 600, 500)
        self.setWindowIcon(QIcon("Logo.ico"))  # Set the window icon
        self.setStyleSheet("background-color: #ECECEC;")

        layout = QVBoxLayout()

        # Add logo
        self.logo_label = QLabel(self)
        self.logo_pixmap = QPixmap("RNS.ico")
        self.logo_label.setPixmap(self.logo_pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo_label)

        self.address_label = QLabel("Select Scanner Device:")
        self.address_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        layout.addWidget(self.address_label)

        self.address_dropdown = QComboBox()
        self.address_dropdown.setFont(QFont("Helvetica", 11))
        self.address_dropdown.setStyleSheet(
            "background-color: #FFFFFF; color: black; padding: 5px; border-radius: 5px;")
        layout.addWidget(self.address_dropdown)

        self.station_label = QLabel("Station ID:")
        self.station_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        layout.addWidget(self.station_label)

        self.station_entry = QLineEdit()
        self.station_entry.setFont(QFont("Helvetica", 11))
        self.station_entry.setStyleSheet("background-color: #FFFFFF; color: black; padding: 5px; border-radius: 5px;")
        layout.addWidget(self.station_entry)

        button_layout = QHBoxLayout()

        self.start_button = QPushButton(" Start ")
        self.start_button.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #28A745; 
                color: white; 
                border-radius: 5px; 
                padding: 5px 10px;
            }
            QPushButton:pressed {
                background-color: #218838;
                border: 1px solid #1C7430;
            }
        """)
        self.start_button.clicked.connect(self.start_scanner)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(" Stop ")
        self.stop_button.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #DC3545; 
                color: white; 
                border-radius: 5px; 
                padding: 5px 10px;
            }
            QPushButton:pressed {
                background-color: #C82333;
                border: 1px solid #B21F2D;
            }
        """)
        self.stop_button.clicked.connect(self.stop_scanner)
        button_layout.addWidget(self.stop_button)

        self.exit_button = QPushButton(" Exit ")
        self.exit_button.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #343A40; 
                color: white; 
                border-radius: 5px; 
                padding: 5px 10px;
            }
            QPushButton:pressed {
                background-color: #23272B;
                border: 1px solid #1D2124;
            }
        """)
        self.exit_button.clicked.connect(self.exit_app)
        button_layout.addWidget(self.exit_button)

        layout.addLayout(button_layout)

        self.log_display = QTextEdit()
        self.log_display.setFont(QFont("Courier New", 11))
        self.log_display.setStyleSheet("background-color: #2D2D3C; color: white; padding: 10px; border-radius: 5px;")
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Populate dropdown after setting up the UI elements
        self.populate_dropdown()

    def populate_dropdown(self):
        self.log_display.append("Fetching connected Bluetooth devices...\n")
        self.discovery_thread = DeviceDiscoveryThread()
        self.discovery_thread.devices_discovered.connect(self.update_dropdown)
        self.discovery_thread.start()

    def update_dropdown(self, connected_devices):
        if connected_devices:
            self.log_display.append("Connected Bluetooth devices:\n")
            for addr, name in connected_devices:
                if name.startswith("RS"):
                    self.address_dropdown.addItem(f"{name} - {addr}")
                    self.log_display.append(f"  {addr} - {name}\n")
        else:
            self.log_display.append("No connected Bluetooth devices found.\n")

    def start_scanner(self):
        selected_device = self.address_dropdown.currentText().split(" - ")[-1].strip()
        station_id = self.station_entry.text().strip()
        if not selected_device:
            self.log_display.append("Please select a Scanner device.\n")
            return
        if not station_id:
            self.log_display.append("Please enter a Station ID.\n")
            return

        self.scanner_simulator = ScannerSimulator(selected_device, station_id, self.log_display)
        self.scanner_simulator.start()

    def stop_scanner(self):
        if self.scanner_simulator:
            self.scanner_simulator.stop()
            self.scanner_simulator = None

    def exit_app(self):
        if self.scanner_simulator:
            self.scanner_simulator.stop()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(236, 236, 236))  # Light grey background
    palette.setColor(QPalette.WindowText, Qt.black)
    palette.setColor(QPalette.Base, QColor(45, 45, 60))  # Dark background for text edit
    palette.setColor(QPalette.AlternateBase, QColor(236, 236, 236))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.black)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))  # Dark grey buttons
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    main_window = App()
    main_window.show()
    sys.exit(app.exec_())
