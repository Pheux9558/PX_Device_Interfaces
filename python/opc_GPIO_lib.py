import time
import os

# PX libs

import connection_organiser_with_opc as conorg
import timer
import mapping


class GPIOlib(conorg.ConnectionOrganiser):
    def __init__(self, device_name: str = None, firmware: str = None, opc_node_addr: str = "ns=3;", **kwargs):
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
        self.configure_io_file_path = "../sys_files/" + self.program_name_GPIOlib + "/" + self.name + ".data"
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
        module = self.__check_label(module, "in")
        data = self.input_data.get(module, None)
        if isinstance(data, list):
            data[pin] = value
            self.input_data[module] = data
        self.write(module, force=force)
        pass

    def set_all(self, value: int):
        for module in self.input_data.keys():
            self.write(module, [value for _ in range(16)])

    def read_all(self):
        """
        Read all OPC registers from SPS
        """

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
        module = self.__check_label(module, "out")
        if module:
            if self.auto_io:
                data = self.request_from_device(f'ns=3;s="{module}"."Array"')
                if data:
                    self.output_data[module] = data
        return self.output_data.get(module, None)

    def get(self, module: str, pin: int) -> (int, None):
        """
        Get the value of a pin from a module.\n
        read(module) gets triggered in the process.\n
        This function also sets SW_In to 2 (DIO Read Mode) if required.\n

        :type pin: int
        :type module: str
        :param module:
        :param pin:
        :return:
        """
        if self.input_data.get(self.__check_label(module, "in"), None):
            if not self.input_data.get(self.__check_label(module, "in"))[pin] == 2:
                self.set(self.__check_label(module, "in"), pin, 2, force=True)
                time.sleep(.02)

        module = self.__check_label(module, "out")
        self.read(module)
        return self.output_data.get(module, [None for _ in range(16)])[pin]


# region Test section
if __name__ == '__main__':
    tmr = timer.Timer()
    test = 6
    module_name = "1K1"
    cycles = 0

    if test == 1:
        temp = GPIOlib("test_bench_NE13", debug=True, init_connect=True, pre_config_io=True, auto_io=True)
        print(temp.input_data)
        print(temp.output_data)

        temp.set(module_name, 5, 1)
        time.sleep(1)
        temp.set(module_name, 5, 0)
        time.sleep(1)
        print(temp.get(module_name, 0))
        print(temp.read(module_name))
        time.sleep(1)
        temp.disconnect()

    if test == 2:
        temp = GPIOlib("test_bench_NE13", debug=True, init_connect=True, pre_config_io=True, auto_io=True)
        temp.test()
        temp.set(module_name, 0, 0, True)
        time.sleep(1)
        temp.get(module_name, 0)
        time.sleep(1)
        temp.disconnect()

    if test == 3:
        temp = GPIOlib("test_Cabinet_NE13", debug=True, init_connect=True, pre_config_io=True, auto_io=True)
        # temp.test()
        # time.sleep(1)
        tmr.start()

        print(temp.settings_file_path)


        def write_all(m_name, val):
            for pin in range(0, 16):
                temp.set(m_name, pin, val)


        module_names = [
            "K6381",
            "K6391",
            "K6401",
            "K6411",
            "K6421",
            "K6431",
            "K4111",
            "K4121",
            "K4131",
            "K4141",
            "K4151",
            "K4161",
            "K4171",
            "K4201",
            "K4211",
            "K4221",
            "K4231",
            "K4241",
            "K4251",
            "K4261",
            "K4271",
            "K4301",
            "K4311",
            "K4321",
            "K4331",
            "K4341",
            "K4351",
            "K4361",
            "K4371"

        ]

        for name in module_names:
            write_all(name, 1)
            cycles += 16

        temp.set("K4371", 7, 1)
        while temp.get(module_names[-1], 15) == 0:
            time.sleep(.1)
            print("loop")

        for name in module_names:
            write_all(name, 0)
            cycles += 16

        while temp.get(module_names[-1], 15) == 1:
            time.sleep(.1)
            print("loop")

        # time.sleep(1)
        temp.disconnect()

    if test == 4:
        temp = GPIOlib("test_Cabinet_NE13", debug=True, init_connect=True, pre_config_io=True, auto_io=True)
        tmr.start()
        temp.set_all(1)

        temp.set("K4371", 7, 1)
        while temp.get("K4371", 15) == 0:
            time.sleep(.1)
            print("loop")

        temp.set_all(0)
        while temp.get("K4371", 15) == 1:
            time.sleep(.1)
            print("loop")

        temp.disconnect()
    #
    #
    #
    if test == 5:
        def flash_all(m_name):
            for pin in range(0, 16):
                temp.set(m_name, pin, 1)
                time.sleep(.25)
                temp.set(m_name, pin, 2)


        module_names = [
            "K4111",
            "K4121",
            "K4131"
        ]

        temp = GPIOlib("test_Cabinet_NE13", debug=True, init_connect=True, pre_config_io=True, auto_io=True)
        for name in module_names:
            flash_all(name)

        time.sleep(.1)
        temp.disconnect()

    if test == 6:  # Mapping test
        p_map = mapping.PlugMap()


        def flash_all_plug(x_name):
            for x_pin in range(1, 25):
                m_name, m_pin = p_map.map(x_name, x_pin)
                print(f'Module: {m_name}, Pin out: {m_pin}')
                temp.set(m_name, m_pin, 1)
                time.sleep(.25)
                temp.set(m_name, m_pin, 2)

        def pause_while(m_name, m_pin, val=0):
            print(f'Pause for {m_name} at {m_pin}')
            while temp.get(m_name, m_pin) == val:
                time.sleep(.1)

        def flash_all_plug_cross_test(x_name_out, x_name_in):
            for x_pin in range(1, 25):
                m_name_out, m_pin_out = p_map.map(x_name_out, x_pin)
                m_name_in, m_pin_in = p_map.map(x_name_in, x_pin)

                print(f'Module: {m_name_out}, Pin out: {m_pin_out}')
                temp.set(m_name_out, m_pin_out, 1)
                pause_while(m_name_in, m_pin_in, 0)
                time.sleep(.05)
                temp.set(m_name_out, m_pin_out, 2)
                pause_while(m_name_in, m_pin_in, 1)
                time.sleep(.05)


        plug_names_str =\
            """
            X4250, X4265
            X4300, X4315
            X4110, X4125
            X4140, X4155
            X4330, X4345
            X4360, X4375
            X4170, X4205
            X4220, X4235
            X5200, X5215
            X5230, X5245
            X5010, X5025
            X5040, X5055
            X5260, X5275
            X5310, X5325
            X5070, X5105
            X5120, X5135
            X5340, X5355
            X5370, X6175
            X5150, X5165
            X6005, X6020
            X6210, X6225
            X6240, X6255
            X6035, X6050
            X6065, X6100
            X6270, X6305
            X6320, X6335
            X6115, X6130
            X6145, X6160
            X6350, X6365
            
            """
        plug_names = plug_names_str.split("\n")
        plug_names = [x.replace(" ", "").split(",") for x in plug_names if x != ""]

        # plug_names.pop(-1)

        temp = GPIOlib("test_Cabinet_NE13", debug=False, init_connect=True, pre_config_io=True, auto_io=True)
        temp.set_all(2)
        print("Set parameter for all modules")
        time.sleep(3)
        plug_start = 0
        # max 29
        plug_stop = 1

        for index in range(plug_start, plug_stop):
            print("###################################################")
            print(f'Plug in adapter from {plug_names[index][0]} to {plug_names[index][1]}')
            print("###################################################")
            flash_all_plug_cross_test(plug_names[index][0], plug_names[index][1])
            flash_all_plug_cross_test(plug_names[index][1], plug_names[index][0])
        # for name in plug_names[plug_set]:
        #     flash_all_plug(name)

        time.sleep(.1)
        temp.disconnect()
    #
    #
    tmr.stop(cycles)
# endregion
