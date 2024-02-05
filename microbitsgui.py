import tkinter as tk

from layer4 import TCP_Handler
from layer2 import Layer2, SerialReaderProtocolLine, ReaderThread
import json

from microbitsmodule import get_micro



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
    layer_2 = Layer2(serial_port,layer4=None) #this is hacky but it works
    layer_6 = ChatStream(main_frame)
    layer_4 = TCP_Handler(serial_port,layer_6)
    layer_2.layer4 = layer_4
    # Set listener to our reader
    SerialReaderProtocolLine.frame_handler =  layer_2
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