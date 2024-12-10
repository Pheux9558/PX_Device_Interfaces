import os
import time

from PyQt6.QtWidgets import QApplication, QFileDialog
import PX_Device_Interfaces as px


class Update:
    def __init__(self):
        self.arduino = px.connection_organiser_with_opc.ConnectionOrganiser(
                    "test", debug=False, init_connect=True, send_attach="")

    def upload_new_fw(self, bin_file: str, buf_size = 64):
        if not self.arduino.connected:
            self.arduino.open_config_window()

        if not self.arduino.connected:
            return

        self.arduino.send("newfw")

        with open(bin_file, mode='rb') as file:
            line = file.readline(buf_size)
            while line:
                self.arduino.send(line)
                print(line)
                line = file.readline(buf_size)
        self.arduino.send("uploadeDone")
        self.loop_while_upload()


    def to_device(self, project_path):
        if not self.arduino.connected:
            self.arduino.open_config_window()

        if self.arduino.connected:
            index = 0
            self.arduino.send("b\n")
            while True:
                full_path = os.path.join(project_path, f'{index}.bin')
                print(full_path)
                if not os.path.exists(full_path):
                    break
                if index != 0:
                    self.arduino.send("n\n")

                with open(full_path, "r") as file:
                    lines = file.readlines()
                    self.arduino.send("a\n")
                    for line in lines:
                        self.arduino.send(line)
                index += 1

            self.arduino.send("e\n")
            self.loop_while_upload()

    def loop_while_upload(self):
        max_value = self.arduino.send_q.qsize()
        try:
            while self.arduino.send_q.qsize():
                time.sleep(.05)
                print(f"Progress: [{max_value - self.arduino.send_q.qsize()}/{max_value}]\r")


        except Exception as e:
            print(e)

if __name__ == "__main__":
    # with open("sys_files/firmware.bin", mode='rb') as file:
    #     line = file.readline(64)
    #     while line:
    #         print(line)
    #         line = file.readline(64)
    u = Update()
    print(u.arduino.connected)
    u.upload_new_fw("sys_files/firmware.bin")
    print("DONE")
    time.sleep(5)

