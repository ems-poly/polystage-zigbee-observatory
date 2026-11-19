"""Small TI ZNP codec shared by the ESP32 firmware and host-side tests."""
def encode(command0,command1,payload=b''):
    body=bytes((len(payload),command0,command1))+payload
    checksum=0
    for value in body: checksum^=value
    return b'\xfe'+body+bytes((checksum,))

class Frames:
    def __init__(self): self.buffer=bytearray()
    def feed(self,data):
        self.buffer.extend(data); output=[]
        while self.buffer:
            if self.buffer[0]!=254: del self.buffer[0]; continue
            if len(self.buffer)<5: break
            length=self.buffer[1]+5
            if len(self.buffer)<length: break
            packet=bytes(self.buffer[:length]); checksum=0
            for value in packet[1:]: checksum^=value
            if checksum:
                del self.buffer[0]; continue
            output.append((packet[2],packet[3],packet[4:-1]));del self.buffer[:length]
        return output

def scan_payload(duration=2):
    return b'\x00\xf8\xff\x07'+bytes((0,duration,0,32))+b'\x00'*11

def energy(data):
    if len(data)<10 or data[0]!=0 or data[2]!=0 or data[3]!=0:
        raise ValueError('Invalid MAC energy scan confirmation')
    if any(data[4:8]): raise ValueError('Some channels were not scanned')
    count,maximum=data[8:10];values=data[10:]
    if len(values)<maximum or count>maximum: raise ValueError('Truncated energy scan')
    if count==16: readings=values[:16]
    elif count==27 and values[:11]==b'\xff'*11: readings=values[11:27]
    else: raise ValueError('Unsupported energy channel mapping')
    return [{'channel':11+i,'raw':value,'percent':round(value*100/255,1)} for i,value in enumerate(readings)]
