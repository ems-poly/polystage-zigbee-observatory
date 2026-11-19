#pragma once
#include <vector>
#include <array>
#include <cstdint>
namespace SurveyRadio {
struct Frame {uint8_t c0,c1;std::vector<uint8_t> data;};
inline std::vector<uint8_t> encode(uint8_t c0,uint8_t c1,const std::vector<uint8_t>& data={}) {
 std::vector<uint8_t> packet{0xfe,static_cast<uint8_t>(data.size()),c0,c1};
 packet.insert(packet.end(),data.begin(),data.end());uint8_t sum=0;
 for(size_t i=1;i<packet.size();++i)sum^=packet[i];packet.push_back(sum);return packet;
}
class Parser {
 std::vector<uint8_t> buffer;
public:
 void clear(){buffer.clear();}
 std::vector<Frame> feed(const uint8_t* data,size_t count){
  buffer.insert(buffer.end(),data,data+count);std::vector<Frame> out;
  while(!buffer.empty()){
   if(buffer[0]!=0xfe){buffer.erase(buffer.begin());continue;}
   if(buffer.size()<5)break;size_t length=buffer[1]+5;if(buffer.size()<length)break;
   uint8_t checksum=0;for(size_t i=1;i<length;++i)checksum^=buffer[i];
   if(checksum){buffer.erase(buffer.begin());continue;}
   out.push_back({buffer[2],buffer[3],{buffer.begin()+4,buffer.begin()+length-1}});
   buffer.erase(buffer.begin(),buffer.begin()+length);
  }
  return out;
 }
};
inline std::vector<uint8_t> scanPayload(){return {0x00,0xf8,0xff,0x07,0,2,0,32,0,0,0,0,0,0,0,0,0,0,0};}
inline bool energy(const std::vector<uint8_t>& d,std::array<uint8_t,16>& out){
 if(d.size()<10||d[0]||d[2]||d[3]||d[4]||d[5]||d[6]||d[7]||d[8]>d[9]||d.size()<size_t(10+d[9]))return false;
 size_t offset=10;
 if(d[8]==27){for(size_t i=10;i<21;++i)if(d[i]!=255)return false;offset=21;}
 else if(d[8]!=16)return false;
 if(d.size()<offset+16)return false;
 for(size_t i=0;i<16;++i)out[i]=d[offset+i];return true;
}
}
