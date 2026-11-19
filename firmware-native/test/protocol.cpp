#include <cstddef>
#include <cassert>
#include "radio_protocol.h"
using namespace SurveyRadio;
int main(){
 Parser p;auto a=encode(0x62,0x0c,{0});std::vector<uint8_t> d(42,0);
 d[8]=27;d[9]=32;for(int i=10;i<21;i++)d[i]=255;
 for(int i=0;i<16;i++)d[21+i]=i+51;
 auto b=encode(0x42,0x8c,d);
 assert(p.feed(a.data(),3).empty());
 std::vector<uint8_t> rest(a.begin()+3,a.end());rest.insert(rest.end(),b.begin(),b.end());
 auto frames=p.feed(rest.data(),rest.size());assert(frames.size()==2);
 std::array<uint8_t,16> values;assert(energy(frames[1].data,values));assert(values[0]==51&&values[15]==66);
 b.back()^=1;b.insert(b.end(),a.begin(),a.end());frames=p.feed(b.data(),b.size());assert(frames.size()==1&&frames[0].c0==0x62);
 d[4]=1;assert(!energy(d,values));assert(scanPayload().size()==19);
}
