import tkinter as tk

from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader

import threading
import time

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
        #print(f"{self.current_packet_num=}")
        if self.num_packets_to_receive ==0:
            try:
                self.num_packets_to_receive = int(line)# int autostrips after testing it, btu id rather strip before
            except ValueError as e:
                print("error receiving this message", e)
            timeout = threading.Thread(daemon= True,target=self.timeout)
            timeout.start()
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
                        print(f"Oh no, we skipped a packet! {self.current_packet_num =}, {next_packet_number=}")
                        self.failed_packet_nums.add(self.current_packet_num)
                        self.current_packet_num = next_packet_number
                    self.distance_into_packet +=1
                except ValueError:
                    #likely dropped a packet
                    self.failed_packet_nums.add(self.current_packet_num)
                    print(f"uh oh, dropped packet! {self.current_packet_num=}, {line=}")
                    # this will trigger many false positives but if we dropped packets we better make sure we dont drop any more
            else:
                if line[0]=="#": # payload
                    self.current_packet.append(line[1:])
                    self.distance_into_packet +=1
                else:
                    try:
                        next_packet_number = int(line)# if this succeeds then its likely the previous packet was dropped
                        #we need to flush and reset
                        print(f"uh oh, dropped packet! {self.current_packet_num=}, {next_packet_number=}")
                        self.failed_packet_nums.add(self.current_packet_num)
                        self.current_packet_num = next_packet_number
                        self.reset_packet()
                    except ValueError:
                        print(f"Error reading line {line}")
                        self.failed_packet_nums.add(self.current_packet_num)
                        self.distance_into_packet +=1

        if self.distance_into_packet ==LINES_PER_PACKET: #0 index, but this is after incrementing
            self.successful_packets[self.current_packet_num] = ("".join(self.current_packet))
            self.successful_packet_nums.add(self.current_packet_num)
            self.reset_packet()
            # nice! we just handled a packet, are there any errors left?
            self.failed_packet_nums.difference_update(self.successful_packet_nums)
            if not self.error_correcting and self.current_packet_num ==self.num_packets_to_receive: #ok so we just handled "all" packets, are there any errors
                if self.failed_packet_nums:
                    self.error_correcting = True
                    self.num_packets_to_receive = len(self.failed_packet_nums)
                    print("error receiving packets",self.failed_packet_nums)
                    print(f"{self.successful_packets=}")
                else:# yoo no errors
                    msg = "".join(self.successful_packets[i] for i in sorted(self.successful_packet_nums))
                    self.handle_message(msg)
                    self.reset_message()
            
                

    def handle_message(self,message):
        full_message = json.loads(message) #why operate on strings??, as lower levels kina needs it at the moment, im im not sure at this point how that code works ¯\_(ツ)_/¯
        if full_message["type"] == 4: #pain text message, used to demmo why it's insecure
            # Execute our callback in tk
            self.tk_listener.after(0, self.tk_listener.on_data, f'(Plaintext){full_message["username"]} >{full_message["message"]}')
        else:
            print("unknown message type received", full_message)
    def reset_packet(self):
        self.distance_into_packet = 0
        self.current_packet = []
    
    def timeout(self):
        time.sleep(0.5)
        if len(self.successful_packet_nums)!= self.num_packets_to_receive:
            self.failed_packet_nums = set(range(1,self.num_packets_to_receive+1)).difference(self.successful_packet_nums)
            print("Timed out!")
            print("error receiving packets",self.failed_packet_nums)
            print(f"{self.successful_packets=}")
            self.reset_packet()

    def reset_message(self):
        self.num_packets_to_receive = 0
        self.successful_packet_nums = set()
        self.failed_packet_nums=set()
        self.successful_packets= {}
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
            self.port.write(b'#'+packet[index:index+MAX_LINE_LENGTH]+b"\r\n")
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