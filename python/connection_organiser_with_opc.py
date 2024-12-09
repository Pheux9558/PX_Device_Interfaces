import tkinter as tk
import os
import socket
import time
import queue
import threading
import serial
import opcua
from opcua import ua


class ConnectionOrganiser:
    def __init__(self, device_name: str, firmware: str = None, init_connect: bool = False, **kwargs):
        """
        Init the connection between this system and PX Systems running GPIO_Lib or CNZero.\n
        Version 2.0 Working with OPC-UA Client

        :type device_name: str          # Define the name of the device. Name of config files
        :type firmware: str             # Define a firmware to ensure connecting the correct device
        :type init_connect: bool        # Connect the System on init
        """
        # -------------------- #
        # Variable declaration #
        # -------------------- #

        # region Variable declaration
        self.name = device_name
        self.program_name = "Connection_Organiser"
        self.settings_file_path = "sys_files/" + self.program_name + "/" + self.name + ".data"
        self.connected = False
        self.firmware = firmware
        self.debug = False
        self.send_worker_phase: int = 0
        self.rec_worker_phase: int = 0

        #

        # type (USB/WIFI/Bluetooth/OPC)
        self.type: (str, None) = None  # USB/WIFI/BLUETOOTH/OPC
        # USB Var
        self.usb_port = ""
        self.usb_baud = ""

        # WIFI Var
        self.wifi_host = ""
        self.wifi_port = ""

        # BLE Var
        #
        #
        #

        # OPC Var
        #
        #
        self.opc_client_address = ""

        self.send_q = queue.Queue()
        self.event_send_block = threading.Event()

        #
        self.receive_q = queue.Queue()

        #
        # endregion

        for key, value in kwargs.items():
            setattr(self, key, value)
        #
        #
        #

        self.do_save = False
        # get settings file with name, read it and connect to device
        if os.path.isfile(self.settings_file_path):
            print(os.path.abspath(self.settings_file_path))
            with open(self.settings_file_path) as settings_file:
                settings_line = settings_file.readline().strip("\n")
                while settings_line:
                    key, value = settings_line.split(":", 1)
                    if self.debug:
                        print(f'INFO: Settings [key:{key}, value:{value}] [{self.name}]')
                    setattr(self, key, value)
                    settings_line = settings_file.readline().strip("\n")
        else:
            print(f'[{self.program_name}] Create system file: {self.settings_file_path} [{self.name}]')
            try:
                os.makedirs("sys_files/" + self.program_name)
            except:
                pass
            with open(self.settings_file_path, "w") as file:
                file.write(
                    f'type:N/A\n'
                    f'usb_port:COM3\n'
                    f'usb_baud:115200\n'
                    f'wifi_host:0.0.0.0\n'
                    f'wifi_port:0000\n'
                    f'opc_client_address:N/A'
                    )
            # self.open_config_window()

        #
        if self.debug:
            Debug(self)

        # init connection
        if init_connect:
            self.connect()

        #
        # TODO set class var to indicate status (No Config/Config but no Connection/Connection)
        #

    def open_config_window(self):
        """
        Helper function to trigger the Configuration window
        """
        self.old_type = self.type
        self.conf = ConfigWindow(self)
        self.new_type = self.type
        self.type = self.old_type
        if self.connected:
            self.disconnect()
            time.sleep(.1)
        self.type = self.new_type
        self.connect()

        #
        #
        #

    def connect(self):
        """
        Connect a device based on the configuration.\n
        currently supported is USB, Wi-Fi, OPC-UA
        Under development Bluetooth
        """
        while self.send_q.qsize() > 0:
            print(f'CON: Q_SEND = {self.send_q.qsize()} [{self.name}]')
            self.send_q.get()
            self.send_q.task_done()
        self.event_send_block.set()

        #
        #
        #

        if self.type == "USB":
            self.connection_usb = serial.Serial()
            self.connection_usb.port = self.usb_port
            self.connection_usb.baudrate = self.usb_baud
            self.connection_usb.timeout = 1
            try:
                self.connection_usb.open()
                if self.debug:
                    print(f'Info: Connection [Type: {self.type}, Object:{self.connection_usb}] [{self.name}]')
                self.connected = True
            except:
                if self.debug:
                    print(f'ERROR: Connection Failed USB [{self.name}]')
                self.connected = False
            time.sleep(2.2)
        #
        #
        #
        elif self.type == "WIFI":
            self.connection_wifi = socket.socket()
            try:
                self.connection_wifi.connect((self.wifi_host, int(self.wifi_port)))
                # self.connection_wifi.setblocking(False)
                if self.debug:
                    print(f'Info: Connection [Type: {self.type}, Object:{self.connection_wifi}] [{self.name}]')
                self.connected = True
            except:
                if self.debug:
                    print(f'ERROR: Connection Failed WiFi [{self.name}]')
                self.connected = False
            time.sleep(1)
        #
        #
        #
        elif self.type == "BLUETOOTH":
            try:
                self.connected = False
            except:
                self.connected = False
        #
        #
        #
        elif self.type == "OPC":
            self.connection_opc_client = opcua.Client(self.opc_client_address)
            try:
                self.connection_opc_client.session_timeout = 30000
                self.connection_opc_client.connect()
                if self.debug:
                    print(f'Info: Connection [Type: {self.type}, Object:{self.connection_opc_client}] [{self.name}]')
                    print(f'Info: Connected to client: {self.opc_client_address} [{self.name}]')
                    print(f'Info: Object root node: {self.connection_opc_client.get_root_node()} [{self.name}]')
                self.connected = True
            except:
                if self.debug:
                    print(f'ERROR: Connection Failed OPC-UA [{self.name}]')
                self.connected = False
        #
        #
        #
        else:
            if self.debug:
                print(f'ERROR: Connection Failed, no type Set [{self.name}]')
            self.connected = False

        if self.connected:
            self.send_thread = threading.Thread(target=self.__send_worker, daemon=True)
            self.send_thread.start()
            if (
                    self.type == "USB" or
                    self.type == "WIFI" or
                    self.type == "BLUETOOTH"
            ):
                self.receive_thread = threading.Thread(target=self.receive_worker, daemon=True)
                self.receive_thread.start()
            self.check_firmware()

    def disconnect(self):
        """
        Disconnect a device
        """
        self.connected = False
        self.clear_send()
        self.event_send_block.set()
        if self.type == "USB":
            if self.debug:
                print(f'Info: Disconnect [Object:{self.connection_usb}] [{self.name}]')
            try:
                self.connection_usb.close()
            except:
                if self.debug:
                    print(f'ERROR: Disconnect Failed [{self.name}]')
        #
        #
        #
        elif self.type == "WIFI":
            if self.debug:
                print(f'Info: Disconnect [Object:{self.connection_wifi}] [{self.name}]')
            try:
                self.connection_wifi.close()
            except:
                if self.debug:
                    print(f'ERROR: Disconnect Failed [{self.name}]')
        #
        #
        #
        elif self.type == "BLUETOOTH":
            try:
                pass
            except:
                if self.debug:
                    print(f'ERROR: Disconnect Failed [{self.name}]')

        elif self.type == "OPC":
            try:
                if self.debug:
                    print(f'Info: Disconnect [Object:{self.connection_opc_client}] [{self.name}]')
                self.connection_opc_client.disconnect()
            except:
                if self.debug:
                    print(f'ERROR: Disconnect Failed [{self.name}]')

    def clear_send(self):
        """
        When disconnecting a device the send buffer must be empty.\n
        False data can cause malfunctions
        """
        if not self.connected:
            while self.send_q.qsize() > 0:
                print(f'Clear send offline failsafe: Q_SEND = {self.send_q.qsize()} [{self.name}]')
                self.send_q.get()
                self.send_q.task_done()
            if self.debug:
                print(f'###Clearing Send Q Done### [{self.name}] Disconnected')
            return
        if self.debug:
            print(f'###Clearing Send Q### [{self.name}]')
            print("Q size: ", self.send_q.qsize())
        while self.send_q.qsize() > 0:
            time.sleep(0.01)
        if self.debug:
            print(f'###Clearing Send Q Done### [{self.name}]')

    def send(self, data_to_send: (str, bytes, list, int), type_of_data: str = "str"):
        """
        Add data to the send Buffer\n\n
        with OPC-UA:\n
        data_to_send["node_id", (str, int, bytes, list)]

        :type type_of_data: object
        :param data_to_send: (str, int, bytes, list)
        """
        if self.connected:
            data_to_send = [type_of_data, data_to_send]
            self.send_q.put(data_to_send)
            if self.debug:
                print(f'send_queue add: {data_to_send} length: {self.send_q.qsize()} [{self.name}]')

    def send_to_device(self, data_to_send: str):
        """
        This function makes old V1 PX systems compatible with Connection Organiser V2 upwards
        :type data_to_send: str
        """
        self.__send_to_device(["str", data_to_send])

    def __send_worker(self):
        """
        Private function
        Thread to catch send requests from the buffer and send it to the device
        """
        if self.debug:
            print(f'Start Send Worker [{self.name}]')
        while self.connected:
            try:
                self.send_worker_phase = 1
                data_to_send: (list, None) = self.send_q.get(True, 1)
            except:
                if self.debug:
                    pass
                    # print(f'Send Worker Q MT [{self.name}]')
                data_to_send = None
            if data_to_send:
                if self.debug:
                    print(f'Get from Q: {data_to_send} [{self.send_q.qsize()}] [{self.name}]')
                self.event_send_block.clear()
                self.__send_to_device(data_to_send)
                self.send_worker_phase = 2
                self.event_send_block.wait(timeout=10)
                if self.debug:
                    print("Send Task done")
                self.send_q.task_done()
        self.send_worker_phase = 3
        print(f'END Send Worker [{self.name}]')

    def __send_to_device(self, data_list_to_send: list):
        """
        Private function.\n
        Function to directly send data to the device.\n
        USB, WIFI and Bluetooth only support str type.\n
        OPC-UA support str, bytes, list, int.
        :type data_list_to_send: list
        :param data_list_to_send:
        """

        type_of_data, data_to_send = data_list_to_send[0], data_list_to_send[1]
        if isinstance(data_to_send, str):
            data_to_send = data_to_send.replace("\n", "")

        if self.connected:
            # region USB WIFI BLE
            # lock for supported type
            if (isinstance(data_to_send, str) and
                    (
                            self.type == "USB" or
                            self.type == "WIFI" or
                            self.type == "BLUETOOTH"
                    )):
                if self.type == "USB":
                    try:
                        if self.debug:
                            print(f'Info: Send [{data_to_send}] [{self.name}]')
                        self.connection_usb.write((data_to_send + "\n").encode())
                    except:
                        print(f'ERROR: Connection Organiser send() [{self.name}]')
                        self.connected = False
                        self.disconnect()
                #
                #
                #
                elif self.type == "WIFI":
                    try:
                        if self.debug:
                            print(f'Info: Send [{data_to_send}] [{self.name}]')
                        self.connection_wifi.send((data_to_send + "\n").encode())
                    except:
                        print(f'ERROR: Connection Organiser [send()] [{self.name}]')
                        self.connected = False
                        self.disconnect()
                #
                #
                #
                elif self.type == "BLUETOOTH":
                    try:
                        if self.debug:
                            print(f'Info: Send [{data_to_send}] [{self.name}]')

                    except:
                        print(f'ERROR: Connection Organiser send() [{self.name}]')
                        self.connected = False
                        self.disconnect()
            # endregion

            # region OPC-UA
            if self.type == "OPC":
                try:
                    node_id, data_to_send = data_to_send[0], data_to_send[1]
                except:
                    if self.debug:
                        print(f'ERROR: Send param invalid: node_id [{self.name}]')
                    # Unlock sender
                    self.event_send_block.set()
                    return
                    #

                # Catch Node from OPC-UA Server

                try:
                    client_node = self.connection_opc_client.get_node(node_id)
                except:
                    print(f'ERROR: Connection Organiser send() [{self.name}]')
                    self.connected = False
                    self.disconnect()
                    return

                client_node_dv = None

                # Generate OPC send data
                # TODO Add missing data types
                if type_of_data == "byte":
                    client_node_dv = ua.DataValue(ua.Variant(data_to_send, ua.VariantType.Byte))

                # If data is available send it
                if client_node_dv:
                    try:
                        client_node.set_value(client_node_dv)
                    except Exception as e:
                        print(
                            f'ERROR [{e}]: Connection Organiser send() [{self.name}]\n'
                        )
                        self.connected = False
                        self.disconnect()
                        return
                    if self.debug:
                        print(f'Set Value of Node [{client_node}]: {data_to_send}')
                else:
                    if self.debug:
                        print(f'ERROR: Send param invalid: type_of_data [{self.name}]')

                # Unlock sender
                self.event_send_block.set()
            # endregion

    def receive_worker(self):
        # print(f'Start Receive Worker [{self.name}]')
        while self.connected:
            receive_char = ""
            if self.connected:
                self.rec_worker_phase = 1
                if self.type == "USB":
                    try:
                        while not receive_char.endswith("\n"):
                            receive_char = self.connection_usb.readline().decode()
                        receive_char = receive_char.replace("\r", "")
                        if self.debug:
                            if receive_char:
                                print(f'Info: Get in Receive [{receive_char}] [{self.name}]')
                    except Exception as e:
                        if self.debug:
                            print(f'ERROR [{e}]: Connection Organiser [receive()] [{self.name}]')
                        self.connected = False
                        self.disconnect()
                #
                #
                #
                elif self.type == "WIFI":
                    try:
                        while not receive_char.endswith("\n"):
                            receive_char += self.connection_wifi.recv(1024).decode()

                        receive_char = receive_char.replace("\r", "")
                        if self.debug:
                            print(f'Info: Get in Receive [{receive_char}] [{self.name}]')

                    except Exception as e:
                        pass
                        if self.debug:
                            print(f'ERROR [{e}]: Connection Organiser receive() [{self.name}]')
                        self.connected = False
                        self.disconnect()
                #
                #
                #
                elif self.type == "BLUETOOTH":
                    try:
                        pass
                    except:
                        self.connected = False
                        self.disconnect()

                if receive_char:
                    self.rec_worker_phase = 2
                    if receive_char.count('>') > 0:
                        self.event_send_block.set()
                        if self.debug:
                            print(f'Event send block = Clear [{self.name}]')
                        # print("ADD")
                    # receive_char = receive_char.replace(">", "")
                    if receive_char:
                        for part in receive_char.split("\n"):
                            if part:
                                if self.debug:
                                    print(f'ADD to receive_q: {part} [{self.name}]')
                                self.receive_q.put(part)

        self.rec_worker_phase = 3
        print(f'END Receive Worker [{self.name}]')

    def request_from_device(self, node_id: str):
        """
        OPC function to read a Node
        :type node_id: str
        """

        if not self.connected:
            return

        if self.type == "OPC":
            try:
                client_node = self.connection_opc_client.get_node(node_id)
                client_node_value = client_node.get_value()
                if self.debug:
                    print(f'Value of Node [{client_node}]: {client_node_value}')
                return client_node_value
            except Exception as e:
                print(f'ERROR [{e}]: Connection Organiser request_from_device() [{self.name}]')
                self.connected = False
                self.disconnect()
                return

    # If firmware is defined run a check
    def check_firmware(self):
        # TODO Update firmware feedback for opc
        if self.firmware:
            self.event_send_block.set()
            self.send("M100")
            time.sleep(0.1)
            # print(flag1 [{self.name}]')
            get_firmware = self.receive_q.get()
            self.receive_q.task_done()
            # print(flag2 [{self.name}]')
            while get_firmware:
                if get_firmware == self.firmware:
                    if self.debug:
                        print(f'Info: Connection [Firmware: {get_firmware}]')
                        print(f'Settings: Connected [{self.name}]')
                    return
                else:
                    if self.debug:
                        print(f'ERROR: Connection Firmware is: {get_firmware}, but need to be: {self.firmware}')
                get_firmware = self.receive_q.get()
                self.receive_q.task_done()
            if self.debug:
                print(f'ERROR: Connection Firmware could not retrieved')
            self.disconnect()


class ConfigWindow:
    def __init__(self, obj):
        self.watched = obj
        self.do_save = False
        self.ui_type: (str, None) = None
        self.window()

    def save_help(self):
        if self.ui_type == "USB":
            self.watched.type = "USB"
        if self.ui_type == "WIFI":
            self.watched.type = "WIFI"
        if self.ui_type == "BLUETOOTH":
            self.type = "BLUETOOTH"
        if self.ui_type == "OPC":
            self.type = "OPC"

        if self.watched.type == "USB":
            if not self.entry_usb_port.get() == "" and not self.entry_usb_baud.get() == "":
                self.watched.usb_port = self.entry_usb_port.get()
                self.watched.usb_baud = self.entry_usb_baud.get()
                self.do_save = True
                self.root.destroy()
            else:
                print("ERROR: Blank Entry")

        if self.watched.type == "WIFI":
            if not self.entry_wifi_host.get() == "" and not self.entry_wifi_port.get() == "":
                self.watched.wifi_host = self.entry_wifi_host.get()
                self.watched.wifi_port = self.entry_wifi_port.get()
                self.do_save = True
                self.root.destroy()
            else:
                print("ERROR: Blank Entry")

        if self.watched.type == "BLUETOOTH":
            a = False
            if a:
                self.do_save = True
                self.root.destroy()
            else:
                print("ERROR: Blank Entry")

        if self.watched.type == "OPC":
            if not self.entry_opc_adress.get() == "":
                self.watched.opc_client_address = self.entry_opc_adress.get()
                self.do_save = True
                self.root.destroy()


    def ui_sw_usb(self):
        self.ui_type = "USB"
        self.btn_usb_frame.config(bg="gray80")
        self.btn_wifi_frame.config(bg="gray94")
        self.btn_ble_frame.config(bg="gray94")
        self.btn_opc_frame.config(bg="gray94")

        #
        self.frame_usb.grid(column=0, row=2, columnspan=3, sticky="nsew")
        self.frame_wifi.grid_remove()
        self.frame_ble.grid_remove()
        self.frame_opc.grid_remove()
        #
        self.entry_usb_port.delete(0, 'end')
        self.entry_usb_port.insert(0, self.watched.usb_port)
        self.entry_usb_baud.delete(0, 'end')
        self.entry_usb_baud.insert(0, self.watched.usb_baud)

    def ui_sw_wifi(self):
        self.ui_type = "WIFI"
        self.btn_usb_frame.config(bg="gray94")
        self.btn_wifi_frame.config(bg="gray80")
        self.btn_ble_frame.config(bg="gray94")
        self.btn_opc_frame.config(bg="gray94")

        #
        self.frame_usb.grid_remove()
        self.frame_wifi.grid(column=0, row=2, columnspan=3, sticky="nsew")
        self.frame_ble.grid_remove()
        self.frame_opc.grid_remove()
        #
        self.entry_wifi_host.delete(0, 'end')
        self.entry_wifi_host.insert(0, self.watched.wifi_host)
        self.entry_wifi_port.delete(0, 'end')
        self.entry_wifi_port.insert(0, self.watched.wifi_port)

    def ui_sw_ble(self):
        self.ui_type = "BLUETOOTH"
        self.btn_usb_frame.config(bg="gray94")
        self.btn_wifi_frame.config(bg="gray94")
        self.btn_ble_frame.config(bg="gray80")
        self.btn_opc_frame.config(bg="gray94")
        #
        self.frame_usb.grid_remove()
        self.frame_wifi.grid_remove()
        self.frame_ble.grid(column=0, row=2, columnspan=3, sticky="nsew")
        self.frame_opc.grid_remove()

    def ui_sw_opc(self):
        self.ui_type = "OPC"

        self.btn_usb_frame.config(bg="gray94")
        self.btn_wifi_frame.config(bg="gray94")
        self.btn_ble_frame.config(bg="gray94")
        self.btn_opc_frame.config(bg="gray80")

        self.frame_usb.grid_remove()
        self.frame_wifi.grid_remove()
        self.frame_ble.grid_remove()
        self.frame_opc.grid(column=0, row=2, columnspan=3, sticky="nsew")

        self.entry_opc_adress.delete(0, 'end')
        self.entry_opc_adress.insert(0, self.watched.opc_client_address)


    def window(self):
        self.root = tk.Tk()
        self.root.geometry('480x300')
        self.temp = tk.Label(self.root, width=0, height=0)
        self.temp.grid(column=0, row=0, columnspan=10, sticky="nsew")
        self.root.title(f'{self.watched.program_name}:{self.watched.name}')
        self.root.resizable(False, False)

        #
        #
        #

        self.btn_usb_frame = tk.Button(self.root, text="Config\nUSB",
                                       state='active', command=self.ui_sw_usb,
                                       width=10, height=0, font=('Helvetica bold', 10))
        self.btn_usb_frame.grid(column=0, row=1, sticky="nsew", padx=15, pady=10)
        self.frame_usb = tk.Frame(self.root, height=200)  # , bg="#bcbcba"
        self.label_usb_port = tk.Label(self.frame_usb, width=10, text="Port:")
        self.label_usb_port.grid(column=0, row=0, sticky="nsew", padx=15, pady=10)
        self.entry_usb_port = tk.Entry(self.frame_usb)
        self.entry_usb_port.grid(column=1, row=0, sticky="nsew", pady=10)
        self.label_usb_baud = tk.Label(self.frame_usb, width=10, text="Baud:")
        self.label_usb_baud.grid(column=0, row=1, sticky="nsew", padx=15, pady=10)
        self.entry_usb_baud = tk.Entry(self.frame_usb)
        self.entry_usb_baud.grid(column=1, row=1, sticky="nsew", pady=10)

        #
        #
        #

        self.btn_wifi_frame = tk.Button(self.root, text="Config\nWiFi",
                                        state='active', command=self.ui_sw_wifi,
                                        width=10, height=0, font=('Helvetica bold', 10))
        self.btn_wifi_frame.grid(column=1, row=1, sticky="nsew", padx=15, pady=10)
        self.frame_wifi = tk.Frame(self.root, height=200)
        self.label_wifi_host = tk.Label(self.frame_wifi, width=10, text="IP:")
        self.label_wifi_host.grid(column=0, row=0, sticky="nsew", padx=15, pady=10)
        self.entry_wifi_host = tk.Entry(self.frame_wifi)
        self.entry_wifi_host.grid(column=1, row=0, sticky="nsew", pady=10)
        self.label_wifi_port = tk.Label(self.frame_wifi, width=10, text="Port:")
        self.label_wifi_port.grid(column=0, row=1, sticky="nsew", padx=15, pady=10)
        self.entry_wifi_port = tk.Entry(self.frame_wifi)
        self.entry_wifi_port.grid(column=1, row=1, sticky="nsew", pady=10)

        #
        #
        #

        self.btn_ble_frame = tk.Button(self.root, text="Config\nBluetooth",
                                       state='active', command=self.ui_sw_ble,
                                       width=10, height=0, font=('Helvetica bold', 10))
        self.btn_ble_frame.grid(column=2, row=1, sticky="nsew", padx=15, pady=10)
        self.frame_ble = tk.Frame(self.root, bg="#dcbcba", height=200)

        #
        #
        #
        self.btn_opc_frame = tk.Button(
            self.root, text="Config\nOpcUa",
            state='active', command=self.ui_sw_opc,
            width=10, height=0, font=('Helvetica bold', 10))
        self.btn_opc_frame.grid(column=3, row=1, sticky="nsew", padx=15, pady=10)
        self.frame_opc = tk.Frame(self.root, height=200)
        self.label_opc_adress = tk.Label(self.frame_opc, width=10, text="Adress:")
        self.label_opc_adress.grid(column=0, row=0, sticky="nsew", padx=15, pady=10)
        self.entry_opc_adress = tk.Entry(self.frame_opc, width=30)
        self.entry_opc_adress.grid(column=1, row=0, columnspan=10, sticky="nsew", pady=10)


        #
        #
        #
        self.btn_cancel = tk.Button(self.root, text="Cancel", command=lambda: self.root.destroy(), width=10)
        self.btn_cancel.place(anchor="se", x=360 - 110, y=300 - 10)
        self.btn_save = tk.Button(self.root, text="Save", command=self.save_help, width=10)
        self.btn_save.place(anchor="se", x=360 - 10, y=300 - 10)

        #
        #
        #

        if self.watched.type == "USB":
            self.ui_sw_usb()
        if self.watched.type == "WIFI":
            self.ui_sw_wifi()
        if self.watched.type == "BLUETOOTH":
            self.ui_sw_ble()
        if self.watched.type == "OPC":
            self.ui_sw_opc()

        self.root.mainloop()

        #
        #
        #

        # TODO if save -> write to settings
        if self.do_save:
            self.do_save = False
            #
            #
            with open(self.watched.settings_file_path, "w") as f:
                f.write(f'type:{self.watched.type}\n')

                # Write USB
                f.write(
                    f'type:{self.watched.type}\n'
                    f'usb_port:{self.watched.usb_port}\n'
                    f'usb_baud:{self.watched.usb_baud}\n'
                    f'wifi_host:{self.watched.wifi_host}\n'
                    f'wifi_port:{self.watched.wifi_port}\n'
                    f'opc_client_address:{self.watched.opc_client_address}'
                    )


class Debug:
    def __init__(self, obj):
        self.watched = obj
        self.debug_thread = threading.Thread(target=self.debugger, daemon=True)
        self.debug_thread.start()

    def debugger(self):
        self.root_debugger = tk.Tk()
        self.root_debugger.geometry('360x300')
        self.root_debugger.title(f'DEBUGGER: {self.watched.program_name}:{self.watched.name}')
        self.root_debugger.resizable(False, False)

        self.label_name = tk.Label(self.root_debugger, width=0, height=0,
                                   text=f'{self.watched.program_name}:{self.watched.name}', font=('Helvetica bold', 10))
        self.label_name.grid(column=0, row=0, columnspan=10, sticky="nsew")

        self.label_status = tk.Label(self.root_debugger, width=10, height=1,
                                     text="Status:", font=('Helvetica bold', 15))
        self.label_status.grid(column=0, row=1)

        self.label_status_phase = tk.Label(self.root_debugger, width=10, height=1,
                                           text="Phase", font=('Helvetica bold', 10))
        self.label_status_phase.grid(column=1, row=2)

        self.label_status_running = tk.Label(self.root_debugger, width=10, height=1,
                                             text="Running", font=('Helvetica bold', 10))
        self.label_status_running.grid(column=2, row=2)
        #
        #
        #
        self.label_status_send = tk.Label(self.root_debugger, width=10, height=1,
                                          text="Send Worker", font=('Helvetica bold', 15))
        self.label_status_send.grid(column=0, row=3)

        self.label_status_send_phase = tk.Label(self.root_debugger, width=10, height=1, bg="gray80")
        self.label_status_send_phase.grid(column=1, row=3)

        self.label_status_send_run = tk.Label(self.root_debugger, width=10, height=1, bg="gray80")
        self.label_status_send_run.grid(column=2, row=3)
        #
        #
        #
        self.label_status_rec = tk.Label(self.root_debugger, width=10, height=1,
                                         text="Rec Worker", font=('Helvetica bold', 15))
        self.label_status_rec.grid(column=0, row=4)

        self.label_status_rec_phase = tk.Label(self.root_debugger, width=10, height=1, bg="gray80")
        self.label_status_rec_phase.grid(column=1, row=4)

        self.label_status_rec_run = tk.Label(self.root_debugger, width=10, height=1, bg="gray80")
        self.label_status_rec_run.grid(column=2, row=4)
        #
        #
        #
        self.label_send_q = tk.Label(self.root_debugger, height=1,
                                     text="Send Queue length: 0", font=('Helvetica bold', 15))
        self.label_send_q.grid(column=0, row=5, columnspan=10)
        self.label_rec_q = tk.Label(self.root_debugger, height=1,
                                    text="Receive Queue length: ", font=('Helvetica bold', 15))
        self.label_rec_q.grid(column=0, row=6, columnspan=10)
        #
        #
        #
        while self.root_debugger:
            try:
                if self.watched.send_thread.is_alive():
                    self.label_status_send_run.configure(bg="green")
                else:
                    self.label_status_send_run.configure(bg="yellow")
            except:
                try:
                    self.label_status_send_run.configure(bg="red")
                except:
                    pass
            try:
                if self.watched.receive_thread.is_alive():
                    self.label_status_rec_run.configure(bg="green")
                else:
                    self.label_status_rec_run.configure(bg="yellow")
            except:
                try:
                    self.label_status_rec_run.configure(bg="red")
                except:
                    pass

            try:
                if self.watched.send_worker_phase == 1:
                    self.label_status_send_phase.configure(bg="green")
                if self.watched.send_worker_phase == 2:
                    self.label_status_send_phase.configure(bg="blue")
                if self.watched.send_worker_phase == 3:
                    self.label_status_send_phase.configure(bg="red")
                if self.watched.rec_worker_phase == 1:
                    self.label_status_rec_phase.configure(bg="green")
                if self.watched.rec_worker_phase == 2:
                    self.label_status_rec_phase.configure(bg="blue")
                if self.watched.rec_worker_phase == 3:
                    self.label_status_rec_phase.configure(bg="red")
                self.label_send_q.configure(text=f'Send Queue length: {self.watched.send_q.qsize()}')
                self.label_rec_q.configure(text=f'Receive Queue length: {self.watched.receive_q.qsize()}')
            except:
                pass

            try:
                self.root_debugger.update()
            except:
                pass


if __name__ == "__main__":
    test = 11

    # region Atmel test {1-10}
    if test == 1:
        temp = ConnectionOrganiser(device_name="temp", firmware="GPIO_lib_mega", debug=True)
        # temp.open_config_window()
        # temp.connect()
        # print(temp.connected)
        temp.send("M100")
        temp.send("M300 S255\nM18")
        temp.disconnect()

    if test == 2:
        temp = ConnectionOrganiser(device_name="gpiolib_wifi_test", firmware="GPIO_lib_mega", debug=True)
        if not temp.connected:
            temp.open_config_window()

    if test == 3:
        # temp = ConnectionOrganiser(device_name="gpiolib_wifi_test", debug=False)
        temp = ConnectionOrganiser(device_name="gpiolib_wifi_test", firmware="GPIO_lib_mega", debug=False)
        if not temp.connected:
            temp.open_config_window()

        while temp.connected:
            send_val = input("Send: ")
            if send_val == "Exit":
                break
            else:
                temp.send(send_val)

    if test == 4:
        temp = ConnectionOrganiser(device_name="GPIO_lib_remote", firmware="GPIO_lib_mega", debug=True)
        temp.send("P6 A3")
        temp.send("P6 A1")
        temp.send("Hello")
        while temp.connected:
            send_val = input("Send: ")
            if send_val == "Exit":
                break
            else:
                temp.send(send_val)
    #
    #
    # endregion

    # region OPC-UA test {11-20}
    if test == 11:
        temp = ConnectionOrganiser(device_name="opc_test", firmware=None, init_connect=False, debug=True)
        temp.connect()
        print(temp.connection_opc_client.get_root_node())
        temp.send(['ns=3;s="SW_1K1_In"."Array"', [2, 2, 2, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], "byte")
        time.sleep(1)
        temp.send(['ns=3;s="SW_1K1_In"."Array"', [2, 2, 2, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]], "byte")
        time.sleep(1)
        temp.send(['ns=3;s="SW_1K1_In"."Array"', [2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], "byte")
        time.sleep(1)
        temp.disconnect()

    #
    # endregion

    print("Exit ConnectionOrganiser Loop")
    # exit(-1)
