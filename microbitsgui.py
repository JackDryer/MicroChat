import tkinter as tk

from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader
from layer4 import TCP_Handler

import json

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
        self.tk_listener.after(0, self.tk_listener.on_data, str(data))

class SerialReaderProtocolLine(LineReader): #layers 1  and 2
    tcp_connection = None
    TERMINATOR = b'\r\n'

    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tcp_connection is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        super().connection_made(transport)
        print("Connected, ready to receive data...")

    def handle_line(self, line:str): # so this code is out of our control and line will always be a str
        '''this is layer 2 where we receive frames (in this case its lines), 
        we could apply a hamming code here, but in testing errors within frames seem fairly rare'''
        line = line.strip()
        #print(f"{self.current_packet_num=}")
        '''here we are moving up to layer 4'''
        self.tcp_connection.receive_frame(line)

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

class ChatStream:
    def __init__(self,tk_listener) -> None:
        self.tk_listener = tk_listener
    def handle_message(self,message):
        full_message = json.loads(message) 
        if full_message["type"] == 4: #pain text message, used to demo why it's insecure
            # Execute our callback in tk
            self.tk_listener.after(0, self.tk_listener.on_data, f'(Plaintext){full_message["username"]} >{full_message["message"]}')
        else:
            print("unknown message type received", full_message)
class SendingBox(tk.Entry):
    def __init__(self,tcp_connection,mainFrame:MainFrame,username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Return>",self.send_plaintext)
        self.tcp_connection = tcp_connection
        self.mainFrame= mainFrame
        self.username = username
    
    def send_plaintext(self,_event):
        message = self.get()
        full_message = json.dumps({"type":4,"username":self.username.get(),"message":message})
        self.tcp_connection.send(full_message)
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
    # Initiate serial port
    serial_port = get_micro()
    layer_6 = ChatStream(main_frame)
    layer_4 = TCP_Handler(serial_port,layer_6)
    # Set listener to our reader
    SerialReaderProtocolLine.tcp_connection =  layer_4
    sending_box = SendingBox(layer_4,main_frame,username)
    # Initiate ReaderThread
    reader = ReaderThread(serial_port, SerialReaderProtocolLine)
    #build actual app
    username.grid(sticky="NSEW")
    main_frame.grid(sticky="NSEW",columnspan=2)
    sending_box.grid(sticky="NSEW",columnspan=2)
    # Start reader
    reader.start()
    app.mainloop()