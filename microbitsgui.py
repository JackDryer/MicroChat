import tkinter as tk

from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader

import json

from microbitsmodule import get_micro

username = ""
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
    to_receive = 0
    received = []

    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tk_listener is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        super().connection_made(transport)
        print("Connected, ready to receive data...")

    def handle_line(self, line):
        try:
            if self.to_receive ==0:
                self.to_receive = int(line)
            else:
                """New line waiting to be processed"""
                # Execute our callback in tk
                self.received.append(line.strip().replace("¬", " "))
                self.to_receive -=1
            #if we jsut fininshed reciving a mesage, send it up to be read
            if self.to_receive ==0:
                self.handle_message("".join(self.received))
                self.received = []
        except ValueError as e:
            print("error receiving this message", e)
    def handle_message(self,message):
        full_message = json.loads(message) #why operate on strings??, as lower levels kina needs it at the moment, im im not sure at this point how that code works ¯\_(ツ)_/¯
        if full_message["type"] == 4: #pain text message, used to demmo why it's insecure
            self.tk_listener.after(0, self.tk_listener.on_data, f'(Plaintext){full_message["username"]} >{full_message["message"]}')
        else:
            print("unknown message type received", full_message)

class MainFrame(tk.Frame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listbox = tk.Listbox(self)#
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
        self.listbox.grid(sticky="NSEW")
    def on_data(self, data):
        self.listbox.insert(tk.END, data)
        self.listbox.see("end")

class SendingBox(tk.Entry):
    def __init__(self,port:Serial,mainFrame:MainFrame,username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Return>",self.send_plaintext)
        self.port = port
        self.mainFrame= mainFrame
        self.username = username

    def send_raw(self, message:str):
        message_bytes = message.replace(" ", "¬").encode("utf-8")
        frame_size = 14
        num_frames = (len(message_bytes)/frame_size).__ceil__()
        self.port.write(str(num_frames).encode("utf-8")+b"\r\n")
        for i in range(num_frames):
            index = i*frame_size
            self.port.write(message_bytes[index:index+frame_size]+b"\r\n")
    def send_plaintext(self,_event):
        message = self.get()
        full_message = json.dumps({"type":4,"username":self.username.get(),"message":message})
        self.send_raw(full_message)
        self.mainFrame.on_data("You> "+self.get())
        self.delete(0, 'end')
class Username(tk.Entry):
    def __init__(self,name,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.insert(tk.END,name)
        self.old_name = name
        
if __name__ == '__main__':
    username = input("Enter username:")
    app = tk.Tk()
    username =Username(username)
    app.columnconfigure(0,weight=1)
    app.rowconfigure(1,weight=1)
    main_frame = MainFrame()
    # Set listener to our reader
    SerialReaderProtocolLine.tk_listener = main_frame
    # Initiate serial port
    serial_port = get_micro()
    box = SendingBox(serial_port,main_frame,username)
    # Initiate ReaderThread
    reader = ReaderThread(serial_port, SerialReaderProtocolLine)
    #build actual app
    username.grid(sticky="NSEW")
    main_frame.grid(sticky="NSEW",columnspan=2)
    box.grid(sticky="NSEW",columnspan=2)
    # Start reader
    reader.start()
    app.mainloop()