from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader
class SerialReaderProtocolLine(LineReader): #layers 1  and 2
    frame_handler = None
    TERMINATOR = b'\r\n'

    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.frame_handler is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        super().connection_made(transport)
        print("Connected, ready to receive data...")

    def handle_line(self, line:str): # so this code is out of our control and line will always be a strre'''
        #print(f"{self.current_packet_num=}")
        self.frame_handler.read(line)
SPACE_CHARACTER = "\u0011"
class Layer2:
    def __init__(self,serial,layer4) -> None:
        self.serial = serial
        self.layer4 = layer4
    def read(self,frame:str):
        '''this is layer 2 where we receive frames (in this case its lines), 
        we could apply a hamming code here, but in testing errors within frames seem fairly rare'''
        frame = frame.strip()
        frame = frame.replace(SPACE_CHARACTER," ")
        self.layer4.receive_frame(frame)
    def write(self,frame:str):
        frame = frame.replace(" ",SPACE_CHARACTER)
        print(frame.encode("utf-8")+b"\r\n")
        self.serial.write(frame.encode("utf-8")+b"\r\n")