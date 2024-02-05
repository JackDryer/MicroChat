import threading
import time

PAYLOAD_FRAMES_PER_PACKET = 3
MAX_LINE_LENGTH = 14

class CONTROL:
    MESSAGE_END = "\u0004"
    HEADER = "\u0001"
    PAYLOAD = "\u0002"
    SYN = "\u0016"
    ACK = "\u0006"
    VALID_MESSAGES = {MESSAGE_END,HEADER,PAYLOAD,SYN,ACK}
class Received_Message:
    def __init__ (self,TCP_Handler):
        self.packets =  []
        self.current_packet = None
        self.TCP_Handler = TCP_Handler

    def next_packet (self,next_packet_number:int):
        if self.current_packet is not None:
            print(f"uh oh, something broke {self.current_packet.debug()}")
        self.current_packet = Packet(next_packet_number)

    def add_payload(self,payload):
        if self.current_packet is None:
            return # ignore it, it'll time out and re-send
        self.current_packet.add_payload(payload)
        if self.current_packet.is_complete:
            self.packets.append(self.current_packet.get_payload())
            self.send_ack(self.current_packet)
            self.current_packet = None
    def send_ack(self,packet):
        self.TCP_Handler.send_packet(Packet(self.current_packet.number+1,"ACK"))
    def add_failed_line():
        pass # it already failed, lets just drop it 
    def get_message(self):
        return "".join(self.packets)

        
class Packet:
    def __init__(self, number:int, type = "payload"):
        self.number = number
        self.payload = ""
        self.lines = 0 # this should be marked with a trailer, but for now this'll do
        self.type = type
    def add_payload(self,payload):
        self.payload += payload
        self.lines+=1
    @property
    def is_complete(self) ->bool:
        return self.lines ==PAYLOAD_FRAMES_PER_PACKET
    def get_payload(self):
        return self.payload
    def debug(self):
        return f"{self.type=}, {self.number=}, {self.payload=}"

class TCP_Handler:
    def __init__(self, sending_port,layer_6):
        self.sending_port =sending_port
        self.layer_6= layer_6
        self.current_receiving_message = None
        self.last_received_packet = None # stops duplicates 

    def receive_frame(self,line):
        if not line or line[0] not in CONTROL.VALID_MESSAGES:
            if self.current_receiving_message is not None:
                self.current_receiving_message.add_failed_line()
            return
        if line[0] ==CONTROL.SYN:
            if self.last_received_packet!= "SYN" and self.current_receiving_message: # 2 mesages at once, BAD!
                raise Exception("Tried to handle 2 messages at once")
            self.current_receiving_message = Received_Message(self)
            self.send_packet(Packet(int(line[1:])+1,"ACK"))
            self.last_received_packet = "SYN"
        else:
            self.last_received_packet = None
        match line[0]:
            case CONTROL.HEADER:
                self.current_receiving_message.next_packet(int(line[1:]))
            case CONTROL.PAYLOAD:
                self.current_receiving_message.add_payload(line[1:])
            case CONTROL.MESSAGE_END:
                self.send_packet(Packet(int(line[1:])+1,"ACK"))
                self.layer_6.handle_message(self.current_receiving_message.get_message())
                self.current_receiving_message = None
            case CONTROL.ACK:
                self.receive_ack(int(line[1:]))
                

    def send_packet(self,packet:Packet):
        if packet.type =="ACK": # doesn't need a responce
            self.sending_port.write((CONTROL.ACK+str(packet.number)+"\r\n").encode("utf-8"))
            return
        elif packet.type =="SYN":
            self.sending_port.write((CONTROL.SYN+str(packet.number)+"\r\n").encode("utf-8"))
        elif packet.type =="END":
            self.sending_port.write((CONTROL.MESSAGE_END+str(packet.number)+"\r\n").encode("utf-8"))
        elif packet.type =="payload":
            self.sending_port.write((CONTROL.HEADER+str(packet.number)+"\r\n").encode("utf-8"))
            for i in range(PAYLOAD_FRAMES_PER_PACKET):
                index = i*MAX_LINE_LENGTH
                self.sending_port.write((CONTROL.PAYLOAD+packet.get_payload()[index:index+MAX_LINE_LENGTH]+"\r\n").encode("utf-8"))
        self.timeout = threading.Thread(target=self.timeout_send,args=(packet.number,),daemon=True)
        self.timeout.start()
    def timeout_send(self,number):
        time.sleep(0.5)
        if self.acknowledged == number: #could be a <= but were aking all packets so not an issue 
            print(f"timed out! {self.current_sending_packet.debug()}")
            self.send_packet(self.current_sending_packet)
    def receive_ack(self,number):
        self.acknowledged = number
        packet_size = MAX_LINE_LENGTH*PAYLOAD_FRAMES_PER_PACKET
        index = (self.acknowledged-1)*packet_size # 1 indexed
        payload = self.text_to_send[index:index+packet_size]
        if payload:
            self.current_sending_packet = Packet(number)
            self.current_sending_packet.add_payload(payload)
            self.send_packet(self.current_sending_packet)
        else:
            #finished sending message, close
            if self.text_to_send:
                self.current_sending_packet = Packet(number, "END")
                self.text_to_send = ""
                self.send_packet(self.current_sending_packet)
            # if the text to send is already gone, the connection is now closed

    def send(self,text):
        self.text_to_send  = text
        self.start_sending()
    def start_sending(self):
        self.acknowledged = 0
        self.current_sending_packet = Packet(0,"SYN")
        self.send_packet(self.current_sending_packet)

