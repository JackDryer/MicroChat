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
 
LINES_PER_PACKET = 4
MAX_LINE_LENGTH = 14
class SerialReaderProtocolLine(LineReader): #layers 1  and 2
    tk_listener = None
    TERMINATOR = b'\r\n'
    def __init__(self) -> None:
        super().__init__()
        self.reset_message()
    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tk_listener is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        super().connection_made(transport)
        print("Connected, ready to receive data...")

    def handle_line(self, line:str): # so this code is out of our control and line will always be a str
        line = line.strip()#so long \r\n
        if self.packets_to_receive ==0:
            try:
                self.packets_to_receive = int(line)# int autostrips after testing it, btu id rather strip before
            except ValueError as e:
                print("error receiving this message", e)
        else:
            # build a packet, then add it to successful packets, otherwise store its index
            # if a value is in both succsessfull and failed packets, the fialed one is a false positive
            #self.received.append(line[2:].replace("¬", " ")) # do we need this really?
            if self.distance_into_packet ==0:# new packet
                self.current_packet_num+=1
                try:
                    next_packet_number = int(line)
                    if next_packet_number<0:
                        #negetive packet numbers are corrections    
                        self.current_packet_num = -next_packet_number
                    elif next_packet_number !=self.current_packet_num:
                        self.failed_packet_nums.append(self.current_packet_num)
                        self.current_packet_num = self.next_packet_number
                    self.distance_into_packet +=1
                except ValueError:
                    #likely dropped a packet
                    self.failed_packet_nums.append(self.current_packet_num)
                    # this will trigger many false positives but if we dropped packets we better make sure we dont drop any more
            else:
                try:
                    next_packet_number = int(line)# if this succeeds then its likely the previous packet was dropped
                    #we need to flush and reset
                    self.failed_packet_nums.append(self.current_packet_num)
                    self.current_packet_num = self.next_packet_number
                    self.reset_packet()
                except ValueError:
                    self.current_packet.append(line)
                    self.distance_into_packet +=1
        if self.distance_into_packet ==LINES_PER_PACKET-1: #0 index
            self.successful_packets[self.current_packet_num] = ("".join(self.current_packet))
            self.successful_packet_nums.add(self.current_packet_num)
            self.reset_packet()
            # nice! we just handled a packet, are there any errors left?
            self.failed_packet_nums.difference_update(self.successful_packet_nums)
            if not self.error_correcting and self.current_packet_num ==self.packets_to_receive: #ok so we just handled "all" packets, are there any errors
                if self.failed_packet_nums:
                    self.error_correcting = True
                    self.packets_to_receive = len(self.failed_packet_nums)
                else:# yoo no errors
                    self.handle_message("".join(self.successful_packets[i] for i in sorted(self.successful_packet_nums)))
                    self.reset_message()
            self.packets_to_receive = 0
            
                

    def handle_message(self,message):
        full_message = json.loads(message) #why operate on strings??, as lower levels kina needs it at the moment, im im not sure at this point how that code works ¯\_(ツ)_/¯
        if full_message["type"] == 4: #pain text message, used to demmo why it's insecure
            # Execute our callback in tk
            self.tk_listener.after(0, self.tk_listener.on_data, f'(Plaintext){full_message["username"]} >{full_message["message"]}')
        else:
            print("unknown message type received", full_message)
    def reset_packet(self):
        self.distance_into_packet = 0
        self.packet = []
    def reset_message(self):
        self.packets_to_receive = 0
        self.successful_packet_nums = set()
        self.failed_packet_nums=set()
        self.successful_packets: {}
        self.distance_into_packet = 0
        self.current_packet_num = 0
        self.current_packet = []
        self.error_correcting = False

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
    
    def send_packet(self,number,packet):
        self.port.write(str(number).encode("utf-8")+b"\r\n")
        for i in range(LINES_PER_PACKET-1):
            index = i*MAX_LINE_LENGTH
            self.port.write(packet[index:index+MAX_LINE_LENGTH]+b"\r\n")
    def send_raw(self, message:str):
        #message_bytes = message.replace(" ", "¬").encode("utf-8")
        message_bytes = message.encode("utf-8")
        num_frames = (len(message_bytes)/MAX_LINE_LENGTH).__ceil__()
        num_packets = (num_frames/(LINES_PER_PACKET-1)).__ceil__() #-1 as the first line is the packet number
        self.port.write(str(num_packets).encode("utf-8")+b"\r\n")
        for i in range(num_packets):
            index = i*MAX_LINE_LENGTH*(LINES_PER_PACKET-1)
            self.send_packet(i+1,message_bytes[index:])
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