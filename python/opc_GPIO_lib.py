import time
import os

# PX libs

import PX_Device_Interfaces.python.connection_organiser_with_opc as conorg
import PX_Device_Interfaces.python.timer

class GPIOlib(conorg.ConnectionOrganiser):
    def __init__(self, device_name: str, firmware: str = None, opc_node_addr: str = "ns=3;", **kwargs):
        """
        This class is a ported version of arduino_GPIO_Lib\n
        Versions and functionality may differ between those two\n
        Only works with the OPC-UA IO Firmware for the NE13 Test system\n
        :type device_name: str
        :type firmware: str
        :type kwargs: any
        """

        self.configured = False
        self.pre_config_io = False
        self.auto_io = False
        self.opc_node_addr: str = opc_node_addr
        self.input_data: dict = {}
        self.output_data: dict = {}
        self.inout_label: dict = {}
        self.name = device_name
        self.program_name_GPIOlib = "GPIO_Lib"
        self.configure_io_file_path = "sys_files/" + self.program_name_GPIOlib + "/" + self.name + ".data"
        super().__init__(device_name=device_name, firmware=firmware, **kwargs)
        self.configure_io()
        self.root = self.connection_opc_client.get_root_node() or None

    def open_config_window(self):
        """
        Helper function to reconfigure IO after reconfigure the Connection
        """
        super(GPIOlib, self).open_config_window()
        self.configure_io()

    # TODO open_io_config_window
    @staticmethod
    def open_io_config_window():
        print("NOT IMPLEMENTED")

    def configure_io(self):
        """
        Grab the config file and configure the IO interface\n
        """
        # region Creates file structure if needed
        if not os.path.isfile(self.configure_io_file_path):
            print(f'[{self.program_name_GPIOlib}] Create system file: {self.configure_io_file_path}')
            try:
                os.makedirs("sys_files/" + self.program_name_GPIOlib)
            except:
                pass
            with open(self.configure_io_file_path, "w") as file:
                file.write(
                    "# Syntax Atmega\n"
                    "# >{input/output/input_pullup/servo{number}} {pin number on Arduino} {Custom Name}\n"
                    "#\n"
                    "# Syntax SPS\n"
                    "# >{opcArrayIn/opcArrayIn} {amount off pin in this channel} {Custom name}\n"
                    "#\n"
                    "# !NO BLANK LINES!\n"
                    "#\n"
                )
            self.connected = False
            self.configured = False
            return
        # endregion

        if self.connected or self.pre_config_io:
            with open(self.configure_io_file_path) as configure_io_file:
                configure_io_line = configure_io_file.readline().strip("\n")
                while configure_io_line:
                    configure_io_line = configure_io_line.replace("\n", "")
                    if self.debug:
                        print(f'Config Line: {configure_io_line}')
                    if configure_io_line.startswith(">"):
                        configure_io_line = configure_io_line.replace(">", "")
                        try:
                            use, pin_num, name = configure_io_line.split(" ")
                            if self.debug:
                                print(f'USE: {use}, PIN_NUM: {pin_num}, NAME: {name}')
                        except ValueError:
                            use = None
                            pin_num = None
                            name = None
                            print(f'[{self.program_name_GPIOlib}] INVALID Line: "{configure_io_line}"')

                        if use == "opcArrayIn":
                            self.input_data[name] = [0 for _ in range(int(pin_num))]

                        elif use == "opcArrayOut":
                            self.output_data[name] = [0 for _ in range(int(pin_num))]

                        elif use == "opcArrayInOut":
                            self.input_data[f'{name}_IN_SW'] = [0 for _ in range(int(pin_num))]
                            self.output_data[f'{name}_OUT_SW'] = [0 for _ in range(int(pin_num))]
                            self.inout_label[name] = [f'{name}_IN_SW', f'{name}_OUT_SW']

                    configure_io_line = configure_io_file.readline()

    def test(self):
        """
        Run a sweep on all Software inputs to test Hardware Outputs.\n
        set all Hardware ports to input
        """
        if not self.connected:
            return

        for module in self.input_data.keys():
            module: str
            if module.startswith("K"):
                self.write(module, [2 for _ in range(16)])
        time.sleep(.5)
        for module in self.input_data.keys():
            module: str
            if module.startswith("K"):
                self.write(module, [1 for _ in range(16)])
        time.sleep(.5)
        for module in self.input_data.keys():
            module: str
            if module.startswith("K"):
                self.write(module, [0 for _ in range(16)])
        time.sleep(.5)
        for module in self.input_data.keys():
            module: str
            if module.startswith("K"):
                self.write(module, [2 for _ in range(16)])
        time.sleep(.5)

    def __check_label(self, module: str, mode: str = "") -> str:
        """
        This function helps to find a module with its label.\n
        mode: Send back "in" or "out"
        :rtype: str
        :type module: str
        :type mode: str
        """
        labels: (list, None) = self.inout_label.get(module, None)
        if labels:
            labels: (list, None)
            if mode == "in":
                module = labels[0]
            elif mode == "out":
                module = labels[1]
        return module

    def write_all(self):
        """
        Write all OPC registers to SPS
        """
        if not self.connected:
            return

        if not self.auto_io:
            for module in self.input_data.keys():
                value = self.input_data[module]
                self.send([f'ns=3;s="{module}"."Array"', value], "byte")

    def write(self, module: str, value: (list, None) = None, force: bool = False):
        """
        Write or Overwrite Software Array\n
        return with error if no value set or modul wrong\n
        "force" ignores auto_io.\n
        :type force: bool
        :param force:
        :type module: str
        :type value: list
        :param module:
        :param value:
        """
        if not self.connected:
            return

        module = self.__check_label(module, "in")
        value = value or self.input_data.get(module, None)
        if value:
            if self.auto_io or force:
                self.input_data[module] = value
                self.send([f'ns=3;s="{module}"."Array"', value], "byte")
        else:
            if self.debug:
                print(f"ERROR: No value set [{self.name}]")

    def set(self, module: str, pin: int, value: int, force: bool = False):
        """
        Write Pin of Module.\n
        "force" ignores auto_io.\n
        :type force: bool
        :param force:
        :type module: str
        :type value: list
        :type pin: int
        :param module:
        :param value:
        :param pin:
        """
        if not self.connected:
            return

        module = self.__check_label(module, "in")
        data = self.input_data.get(module, None)
        if isinstance(data, list):
            data[pin] = value
            self.input_data[module] = data
        self.write(module, force=force)

    def set_all(self, value: int):
        if not self.connected:
            return

        for module in self.input_data.keys():
            self.write(module, [value for _ in range(16)])

    def retrieve_pin_value(self, module, pin):
        """
        Retrieve Output value
        """
        if not self.connected:
            return

        module = self.__check_label(module, "in")
        if module:
            data = self.request_from_device(f'ns=3;s="{module}"."Array"')
            if data:
                return data[pin]

    def read_all(self):
        """
        Read all OPC registers from SPS
        """
        if not self.connected:
            return

        if not self.auto_io:
            for module in self.output_data.keys():
                data = self.request_from_device(f'ns=3;s="{module}"."Array"')
                if data:
                    self.output_data[module] = data

    def read(self, module: str) -> any:
        """
        Get Output of specific Module and write it to Output Array.\n
        Return statement gets the raw data.\n

        :type module: str
        :param module:
        """
        if not self.connected:
            return

        module = self.__check_label(module, "out")
        if module:
            if self.auto_io:
                data = self.request_from_device(f'ns=3;s="{module}"."Array"')
                if data:
                    self.output_data[module] = data
        return self.output_data.get(module, None)

    def get(self, module: str, pin: int, do_update_sw_in: bool = True) -> (int, None):
        """
        Get the value of a pin from a module.\n
        read(module) gets triggered in the process.\n
        This function also sets SW_In to 2 (DIO Read Mode) if required and do_update_sw_in is True.\n

        :type pin: int
        :type module: str
        :type do_update_sw_in: bool
        :param module:
        :param pin:
        :param do_update_sw_in:
        :return:
        """
        if not self.connected:
            return

        # Reconfigure input
        if do_update_sw_in:
            if self.input_data.get(self.__check_label(module, "in"), None):
                if not self.input_data.get(self.__check_label(module, "in"))[pin] == 2:
                    self.set(self.__check_label(module, "in"), pin, 2, force=True)
                    time.sleep(.02)

        module = self.__check_label(module, "out")
        self.read(module)
        return self.output_data.get(module, [None for _ in range(16)])[pin]
