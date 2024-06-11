import PX_Device_Interfaces.python.connection_organiser_with_opc as conorg
# import python.connection_organiser_with_opc as conorg
import os
import time

# TODO remove self.use_update, no manual retrieve


class GPIOlib(conorg.ConnectionOrganiser):
    def __init__(self, device_name, firmware=None, **kwargs):
        self.configured = False
        self.auto_io = False
        self.pins = []
        self.names = []
        self.reset_output_pins = []
        self.input_array = []
        self.output_array = []
        self.name = device_name
        self.program_name_GPIOlib = "GPIO_Lib"
        self.configure_io_file_path = "sys_files/" + self.program_name_GPIOlib + "/" + self.name + ".data"
        super().__init__(device_name=device_name, firmware=firmware, **kwargs)
        self.input_array = [[0, 0] for _ in range(0, 70)]
        self.output_array = [[0, 0] for _ in range(0, 70)]
        # print(len(self.input_array))

        self.configure_io()

    #
    #
    #
    def open_config_window(self):
        super(GPIOlib, self).open_config_window()
        self.configure_io()

    def disconnect(self):
        self.lcd_clear()
        for reset_pin in self.reset_output_pins:
            self.digital_write(reset_pin)
        self.lcd_write("GPIO_Lib disconnect")
        time.sleep(0.1)
        super().clear_send()
        self.configured = False
        super().disconnect()

    def configure_io(self):
        if self.connected:
            self.lcd_clear()
            self.lcd_write("I/O Config...")
            self.send("")
            if os.path.isfile(self.configure_io_file_path):
                with open(self.configure_io_file_path) as configure_io_file:
                    configure_io_line = configure_io_file.readline().strip("\n")
                    while configure_io_line:
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

                            # Send pin configuration
                            # M1 input_digital
                            # M2 output
                            # M3 input_pullup
                            # M4 input_analog
                            # M5 servo
                            # M6 LCD NOT USED WIP

                            if use == "input_digital":
                                self.send(f'M1 N{pin_num}')
                            elif use == "output":
                                self.send(f'M2 N{pin_num}')
                                self.reset_output_pins.append(name)
                            elif use == "input_pullup":
                                self.send(f'M3 N{pin_num}')
                            elif use == "input_analog":
                                self.send(f'M4 N{pin_num}')
                            elif use == "servo":
                                name = name.replace("Servo", "").replace("servo", "")
                                self.send(f'M5 N{pin_num} A{name}')
                            elif use == "lcd":
                                try:
                                    w, h = pin_num.split(":")
                                    self.send(f'M6 W{w} H{h}')
                                except:
                                    print(f'[{self.program_name_GPIOlib}] INVALID Line: "{configure_io_line}"')

                            self.pins.append(pin_num)
                            self.names.append(name)
                        configure_io_line = configure_io_file.readline().strip("\n")

                    # clear buffer
                    super().clear_send()
                    self.lcd_clear()
                    self.lcd_write("I/O Config done")
                    self.configured = True
                    if self.debug:
                        print(f'Lists: {self.pins}, {self.names}')
            # If no File -> Create one
            else:
                print(f'[{self.program_name_GPIOlib}] Create system file: {self.configure_io_file_path}')
                os.makedirs("sys_files/" + self.program_name_GPIOlib)
                open(self.configure_io_file_path, "w").close()
        # Failsafe
        else:
            print(f'ERROR: No {self.name} Connection')

    # Used to call pin from name instead of number
    def get_pin_from_name(self, name):
        pin = name
        if type(name).__name__ == "str":
            try:
                pin = self.pins[self.names.index(name)]
            except:
                print(f'Error GPIO Lib: Pin name [{name}] not defined')
        return int(pin)

    # P1 digital_read
    # P2 digital_write
    # P3 analog_read
    # P4 analog_write
    # P5 servo_write
    # P6 LCD commands

    def digital_read(self, pin=None):
        if self.configured:
            if pin:
                pin = self.get_pin_from_name(pin)
                if self.input_array[pin][1] == 0:
                    return False
                else:
                    return True

    def digital_write(self, pin, val=False):
        if self.configured:
            if val:
                val = 1
            elif not val:
                val = 0
            if pin:
                pin = self.get_pin_from_name(pin)
                if not self.output_array[int(pin)][1] == val:
                    self.output_array[pin][1] = int(val)
                    pin = self.get_pin_from_name(pin)
                    self.send(f'P2 N{pin} V{val}')
                    if self.debug:
                        print(f'digital_write: Update pin {pin}')
                        print(f'digital_write: P2 N{pin} V{val}')
                    # self.pause_check()

    def analog_read(self, pin):
        if self.configured:
            if pin:
                pin = self.get_pin_from_name(pin)
                return self.input_array[pin][1]

    def analog_write(self, pin, val):
        if self.configured:
            if pin:
                pin = self.get_pin_from_name(pin)

                if not self.output_array[int(pin)][1] == val:
                    self.output_array[pin][1] = int(val)
                    pin = self.get_pin_from_name(pin)
                    self.send(f'P4 N{pin} V{val}')
                    if self.debug:
                        print(f'digital_write: Update pin {pin}')
                        print(f'analog_write: P4 N{pin} V{val}')

    def servo_write(self, index, val):
        if self.configured:
            self.send(f'P5 N{index} V{val}')
            if self.debug:
                print(f'P5 N{index} V{val}')

    def lcd_write(self, val=" "):
        if self.configured:
            self.send(f'P6 A1')
            self.send(val)
            if self.debug:
                print(f'lcd_write: P6 A1')
                print(f'lcd_write: {val}')

    def lcd_set_cursor(self, x, y):
        if self.configured:
            self.send(f'P6 A2 X{x} Y{y}')
            if self.debug:
                print(f'lcd_set_cursor: P6 A2 X{x} Y{y}')

    def lcd_clear(self):
        if self.configured:
            self.send(f'P6 A3')
            if self.debug:
                print(f'lcd_clear: P6 A3')

    def update_input(self):
        if not self.connected:
            self.configured = False
        update_input = None
        if self.receive_q.qsize() > 0:
            update_input = self.receive_q.get()
        # self.debug = True
        if update_input:
            if self.debug:
                print(f'Update Input Line: {update_input}')
            if update_input.startswith("d"):
                try:
                    pin, val = update_input.replace("d:", "").split(":")
                    self.input_array[int(pin)][1] = int(val)
                    if self.debug:
                        print(f'Digital: pin={pin}, val={val}')
                except Exception as e:
                    if self.debug:
                        print(f'ERROR [{e}]: GPIO_Lib [update_input()]')

            if update_input.startswith("a"):
                try:
                    pin, val = update_input.replace("a:", "").split(":")
                    self.input_array[int(pin)][1] = int(val)
                    if self.debug:
                        print(f'Analog: pin={pin}, val={val}')
                except Exception as e:
                    if self.debug:
                        print(f'ERROR [{e}]: GPIO_Lib [update_input()]')
            self.receive_q.task_done()

        # self.debug = False
    #
#
#
#
#


if __name__ == "__main__":

    def map_val(value, in_min, in_max, out_min, out_max):
        return round(out_min + (((value - in_min) / (in_max - in_min)) * (out_max - out_min)))


    def bat_check():
        read = temp.analog_read("an_bat")
        bat_val = round(map_val(read, 530, 820, 0, 100))
        # print(read)
        if bat_val > 100:
            bat_val = 100
        if bat_val < 0:
            bat_val = 0
        bat_val = str(bat_val) + "%"
        temp.lcd_clear()
        temp.lcd_set_cursor(5, 1)
        temp.lcd_write(str(read))
        temp.lcd_write(" = ")
        temp.lcd_write(bat_val)


    temp = GPIOlib(device_name="SPS_Remote", firmware="GPIO_lib_mega", debug=True, init_connect=True)
    temp.open_config_window()
    # temp = GPIOlib(device_name="GPIO_lib", firmware="GPIO_lib_mega", debug=True)
    if not temp.connected:
        print("Open Config")
        temp.open_config_window()

    import datetime
    log = False
    #####################################
    timer_start = datetime.datetime.now()
    #####################################

    test = 3

    if test == 1:
        if temp.connected:
            temp.digital_write("P15", True)
            while not temp.digital_read("S15") and temp.connected:
                temp.update_input()
                # temp1.analog_write("PWM", map_val(temp1.analog_read("analog"), 0, 1024, 0, 255))

                if temp.digital_read("S0"):
                    temp.digital_write("P0", True)
                else:
                    temp.digital_write("P0")

    if test == 2:
        if temp.connected:
            temp.lcd_clear()
            temp.lcd_write("Test print")
            time.sleep(1)

    if test == 3:
        i = 0
        # print(temp.input_array[0][0])
        temp.debug = True
        temp.digital_write("P15", True)
        while temp.connected and not temp.digital_read("S15"):
            temp.update_input()
            i += 1
            # print(i)
            #
            if temp.digital_read("S14"):

                # bat_check()
                print(temp.analog_read("an_bat"))

    if test == 4:
        if temp.connected:
            temp.lcd_clear()
            for a in range(0, 100):
                temp.lcd_clear()
                temp.lcd_write(str(a))
        time.sleep(1)

    if test == 5:
        # temp.debug = False
        if temp.connected:
            temp.lcd_clear()
            temp.lcd_set_cursor(6, 1)
            temp.lcd_write("PARTY!")
            delay = .0
            test_list = temp.reset_output_pins
            for t in range(0, 10):
                for i in test_list:
                    temp.digital_write(i, True)
                    time.sleep(delay)
                for i in test_list:
                    temp.digital_write(i, False)
                    time.sleep(delay)
                test_list.reverse()

    if test == 6:
        temp.digital_write("P16", True)
        time.sleep(1)
        temp.digital_write("P17", True)
        temp.digital_write("P16")
        time.sleep(1)
        temp.digital_write("P18", True)
        temp.digital_write("P17")
        time.sleep(1)
        temp.digital_write("P18")

    temp.disconnect()

    #####################################
    timer_stop = datetime.datetime.now()
    timer_delta = timer_stop - timer_start
    print(timer_delta)
    if log:
        with open("log_temp.txt", "a") as log_file:
            log_file.write(f'<{timer_delta}>\n')
    #####################################
