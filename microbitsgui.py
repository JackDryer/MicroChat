import tkinter as tk

from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader
from microbitsmodule import get_micro

class SerialReaderProtocolRaw(Protocol):
    tk_listener = None

    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tk_listener is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        print("Connected, ready to receive data...")

    def data_received(self, data):
        """Called with snippets received from the serial port"""
        self.tk_listener.after(0, self.tk_listener.on_data, data.decode())


class SerialReaderProtocolLine(LineReader):
    tk_listener = None
    TERMINATOR = b'\r\n'
    to_recive = 0
    recived = []
    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tk_listener is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        super().connection_made(transport)
        print("Connected, ready to receive data...")

    def handle_line(self, line):
        print(line)
        if self.to_recive ==0:
            self.to_recive = int(line)
        else:
            """New line waiting to be processed"""
            # Execute our callback in tk
            self.recived.append(line.strip().replace("¬", " "))
            self.to_recive -=1
        #if we jsut fininshed reciving a mesage, send it up to be read
        if self.to_recive ==0:
            self.tk_listener.after(0, self.tk_listener.on_data, "Others >"+"".join(self.recived))
            self.recived = []


class MainFrame(tk.Frame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listbox = tk.Listbox(self)#
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
        self.listbox.grid(sticky="NSEW")
        self.grid(sticky="NSEW")

    def on_data(self, data):
        self.listbox.insert(tk.END, data)
        self.listbox.see("end")

class SendingBox(tk.Entry):

    def __init__(self,port:Serial,mainFrame:MainFrame, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Return>",self.send)
        self.port = port
        self.grid(sticky="NSEW")
        self.mainFrame= mainFrame

    def send(self, data):
        message = self.get()
        messagebytes = message.replace(" ", "¬").encode("utf-8")
        frame_size = 14
        num_frames = (len(messagebytes)/frame_size).__ceil__()
        self.port.write(str(num_frames).encode("utf-8")+b"\r\n")
        for i in range(num_frames):
            index = i*frame_size
            self.port.write(messagebytes[index:index+frame_size]+b"\r\n")
        self.mainFrame.on_data("You> "+self.get())
        self.delete(0, 'end')
if __name__ == '__main__':
    app = tk.Tk()
    app.columnconfigure(0,weight=1)
    app.rowconfigure(0,weight=1)
    main_frame = MainFrame()
    # Set listener to our reader
    SerialReaderProtocolLine.tk_listener = main_frame
    # Initiate serial port
    serial_port = get_micro()
    box = SendingBox(serial_port,main_frame)
    # Initiate ReaderThread
    reader = ReaderThread(serial_port, SerialReaderProtocolLine)
    # Start reader
    reader.start()

    app.mainloop()