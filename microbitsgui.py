import tkinter as tk

from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader

import threading
import time

import json

from microbitsmodule import get_micro

username = ""
class CONTROL:
    MESSAGE_START = "\u0091"
    MESSAGE_END = "\u0004"
    HEADER = "\u0001"
    PAYLOAD = "\u0002"
    REQUEST = "\u0005"
    RESPONSE = "\u0006"

    VALID_MESSAGES = {MESSAGE_START,MESSAGE_END,HEADER,PAYLOAD,REQUEST,RESPONSE}


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
        if not line or line[0] not in CONTROL.VALID_MESSAGES: #python is just english
            self.current_packet.add_failed_line()
            return
        if line[0] ==CONTROL.MESSAGE_START:
                if self.current_message: # 2 mesages at once, BAD!
                    raise Exception("Tried to handle 2 messages at once")
                self.current_message = Message(line[1:])
        elif self.current_message:
            self.current_message = Message()
        match line[0]:
            case CONTROL.HEADER:
                self.current_message.next_packet(int(line[1:]))
            case CONTROL.PAYLOAD:
                self.current_message.add_payload(line[1:])
            case CONTROL.REQUEST:
                pass
            case CONTROL.RESPONSE:
                self.current_message.add_correction(line[1:])
        if self.current_message.is_complete:
            self.handle_message(self.current_message.get_message())

    def handle_message(self,message):
        full_message = json.loads(message) #why operate on strings??, as lower levels kina needs it at the moment, im im not sure at this point how that code works ¯\_(ツ)_/¯
        if full_message["type"] == 4: #pain text message, used to demmo why it's insecure
            # Execute our callback in tk
            self.tk_listener.after(0, self.tk_listener.on_data, f'(Plaintext){full_message["username"]} >{full_message["message"]}')
        else:
            print("unknown message type received", full_message)

class Message:
    def __init__ (self,num_packets_to_receive = None):
        timeout = threading.Thread(daemon= True,target=self.timeout)
        timeout.start()
        if num_packets_to_receive is None:
            self.num_packets_to_receive = None # we're gonna time out and then correct 
        try:
            self.num_packets_to_receive = int(num_packets_to_receive)
        except ValueError as e:
            print("error getting number packets", e)
            self.num_packets_to_receive = None
        self.successful_packet_nums = set()
        self.failed_packet_nums=set()
        self.successful_packets= {}
        self.current_packet_num = 0
        self.current_packet = None
        self.handing_errors = False

    def next_packet (self,next_packet_number:int):
        if self.current_packet is not None:
            print(f"uh oh, dropped packet! {self.current_packet_num=}")
            self.failed_packet_nums.add(self.current_packet_num)
        self.current_packet_num+=1
        if next_packet_number !=self.current_packet_num:
            print(f"Oh no, we skipped a packet! {self.current_packet_num =}, {next_packet_number=}")
            self.failed_packet_nums.add(self.current_packet_num)
            self.current_packet_num = next_packet_number

    def add_payload(self,payload):
        if self.current_packet is None:
            self.current_packet_num+=1
            self.failed_packet_nums.add(self.current_packet_num)
            return
        self.current_packet.add_payload(payload)
        if self.current_packet.is_complete:
            self.successful_packets[self.current_packet_num] = self.current_packet.get_payload()
            self.current_packet = None
            self.handle_errors_if_required()
    
    def handle_errors_if_required(self):
        if self.required_to_handle_errors:
            self.handle_errors()
    def handle_errors (self):
        print(f"should handle{self.failed_packet_nums}")
    
    @property
    def required_to_handle_errors(self):
        if self.handing_errors:
            return self.has_errors
        else: return False
        self.failed_packet_nums.difference_update(self.successful_packet_nums)
        return self.error_correcting or self.current_packet_num ==self.num_packets_to_receive
    
    @property
    def has_errors(self):
        if self.num_packets_to_receive is None:
            return True
        return not self.is_complete

    @property
    def is_complete(self) ->bool:
        return len(self.successful_packet_nums)!= self.num_packets_to_receive
    
    def get_message(self):
        return "".join(self.successful_packets[i] for i in sorted(self.successful_packet_nums))

    def timeout(self):
        time.sleep(0.5)
        if not self.is_complete:
            self.failed_packet_nums = set(range(1,self.num_packets_to_receive+1)).difference(self.successful_packet_nums)
            print("Timed out!")
            print("error receiving packets",self.failed_packet_nums)
            print(f"{self.successful_packets=}")
            self.handle_errors()

            if : #ok so we just handled "all" packets, are there any errors
                if self.failed_packet_nums:
                    self.error_correcting = True
                    self.num_packets_to_receive = len(self.failed_packet_nums)
                    print("error receiving packets",self.failed_packet_nums)
                    print(f"{self.successful_packets=}")

        
class Packet:
    def __init__(self, number:int):
        self.number = number
        self.LINES = []
    def add_payload(self,payload):
        self.LINES.append([payload])
    @property
    def is_complete(self) ->bool:
        return len(self.LINES) ==LINES_PER_PACKET
    def get_payload(self):
        return "".join(self.current_packet)
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
    SerialReaderProtocolRaw.tk_listener = main_frame
    # Initiate serial port
    serial_port = get_micro()
    box = SendingBox(serial_port,main_frame,username)
    # Initiate ReaderThread
    reader = ReaderThread(serial_port, SerialReaderProtocolRaw)
    #build actual app
    username.grid(sticky="NSEW")
    main_frame.grid(sticky="NSEW",columnspan=2)
    box.grid(sticky="NSEW",columnspan=2)
    # Start reader
    reader.start()
    app.mainloop()