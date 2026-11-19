#include <Arduino.h>
#include <WiFi.h>
#include <WiFiProv.h>
#include <HTTPClient.h>
#include <esp_wifi.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <sys/time.h>
#include "device_secrets.h"
#include "radio_protocol.h"

constexpr int BUTTON=27,LED_BLUE=2,LED_GREEN=21;
enum class LedMode {Boot,Setup,Zigbee,WifiScan,Connecting,Uploading,Ready,Offline,Error};
volatile LedMode ledMode=LedMode::Boot;
HardwareSerial radio(2);
Preferences prefs;
SurveyRadio::Parser parser;
bool setupMode=false,provisioned=false,pressed=false,held=false;
uint32_t pressAt=0,changeAt=0,lastSurvey=0,rebootAt=0,seq=0,waypoint=0,dropped=0;
bool rawPrevious=true,stableButton=true;
String bootId,location="Survey point 0",lastControl,session;

void lights(bool a,bool b){digitalWrite(LED_BLUE,!a);digitalWrite(LED_GREEN,!b);}
void ledTask(void*){
 LedMode previous=LedMode::Boot;uint32_t changed=millis();
 for(;;){
  LedMode mode=ledMode;if(mode!=previous){previous=mode;changed=millis();}
  uint32_t elapsed=millis()-changed,p;bool blue=false,green=false;
  switch(mode){
   case LedMode::Boot:blue=elapsed%1250<1000;break;
   case LedMode::Setup:blue=(elapsed/200)%2==0;green=!blue;break;
   case LedMode::Zigbee:p=elapsed%1000;blue=p<80||(p>=160&&p<240);break;
   case LedMode::WifiScan:blue=elapsed%1200<600;break;
   case LedMode::Connecting:p=elapsed%2000;blue=p<600&&p%200<100;break;
   case LedMode::Uploading:green=elapsed%250<80;break;
   case LedMode::Ready:green=elapsed%3000<100;break;
   case LedMode::Offline:p=elapsed%3000;green=p<100;blue=p>=300&&p<1300;break;
   case LedMode::Error:p=elapsed%2000;blue=green=(p<900&&p%300<150);break;
  }
  lights(blue,green);vTaskDelay(pdMS_TO_TICKS(20));
 }
}
void button(){
 bool value=digitalRead(BUTTON);uint32_t now=millis();
 if(value!=rawPrevious){rawPrevious=value;changeAt=now;}
 if(now-changeAt>40 && stableButton!=value){
  stableButton=value;
  if(!value){pressed=true;held=false;pressAt=now;}
  else if(pressed){pressed=false;if(!held&&!setupMode){waypoint++;location="Survey point "+String(waypoint);session="";Serial.println("Waypoint: "+location);}}
 }
 if(pressed&&!held&&now-pressAt>=3000){
  held=true;
  if(!setupMode){prefs.putBool("setup",true);Serial.println("Entering BLE setup");delay(100);ESP.restart();}
 }
 if(rebootAt && int32_t(now-rebootAt)>=0)ESP.restart();
}
void waitResponsive(uint32_t duration){uint32_t start=millis();while(millis()-start<duration){button();delay(5);}}
void sendRadio(uint8_t a,uint8_t b,const std::vector<uint8_t>& data={}){auto p=SurveyRadio::encode(a,b,data);radio.write(p.data(),p.size());}
bool awaitRadio(uint8_t a,uint8_t b,std::vector<uint8_t>& result,uint32_t timeout){
 uint32_t start=millis();
 while(millis()-start<timeout){
  button();uint8_t chunk[256];size_t n=0;while(radio.available()&&n<sizeof(chunk))chunk[n++]=radio.read();
  if(n)for(auto &f:parser.feed(chunk,n))if(f.c0==a&&f.c1==b){result=f.data;return true;}
  delay(3);
 }return false;
}
bool pingRadio(){
 for(int i=0;i<10;i++){
  sendRadio(0x21,1);std::vector<uint8_t> out;
  if(awaitRadio(0x61,1,out,1000))return true;
  if(i==3){for(int j=0;j<256;j++)radio.write(0xef);}
 }return false;
}
bool scanRadio(std::array<uint8_t,16>& out){
 parser.clear();while(radio.available())radio.read();sendRadio(0x22,0x0c,SurveyRadio::scanPayload());
 uint32_t start=millis();bool accepted=false,complete=false;
 while(millis()-start<7000){
  button();uint8_t buf[256];size_t n=0;while(radio.available()&&n<sizeof(buf))buf[n++]=radio.read();
  if(n)for(auto &f:parser.feed(buf,n)){
   if(f.c0==0x62&&f.c1==0x0c){if(f.data.empty()||f.data[0])return false;accepted=true;}
   if(f.c0==0x42&&f.c1==0x8c)complete=SurveyRadio::energy(f.data,out);
  }
  if(accepted&&complete)return true;delay(3);
 }return false;
}
double timestamp(){timeval tv;gettimeofday(&tv,nullptr);return double(tv.tv_sec)+tv.tv_usec/1e6;}
void control(JsonDocument &doc){
 double t=doc["unix_time"]|0.0;
 if(t>1700000000){timeval tv{(time_t)t,(suseconds_t)((t-(time_t)t)*1e6)};settimeofday(&tv,nullptr);}
 String next=doc["control"]["location"]|"";
 if(next.length()&&next!=lastControl){location=next;lastControl=next;}
 if(location==lastControl){session=doc["control"]["active_session"].as<String>();if(session=="null")session="";}
}
bool request(const char *path,const String *body=nullptr){
 HTTPClient http;http.setConnectTimeout(2000);http.setTimeout(3000);
 if(!http.begin(String(RECEIVER_URL)+path))return false;
 http.addHeader("X-Survey-Token",INGEST_TOKEN);int status;
 if(body){http.addHeader("Content-Type","application/json");status=http.POST(*body);}else status=http.GET();
 bool ok=status>=200&&status<300;
 if(ok){JsonDocument reply;if(!deserializeJson(reply,http.getString()))control(reply);}
 http.end();return ok;
}
bool connectWifi(){
 ledMode=LedMode::Connecting;WiFi.mode(WIFI_STA);WiFi.begin();uint32_t start=millis();
 while(WiFi.status()!=WL_CONNECTED&&millis()-start<10000){button();delay(10);}
 return WiFi.status()==WL_CONNECTED;
}
void queueSample(const String& payload){
 // Rewrite through a temporary file before replacing the bounded queue.
 File old=LittleFS.open("/queue.jsonl","r");bool trim=old&&old.size()>384*1024;
 File next=LittleFS.open("/queue.tmp","w");if(!next){Serial.println("Queue write failed");return;}
 size_t target=trim?old.size()/2:0;
 while(old&&old.available()){
  String line=old.readStringUntil('\n');
  if(trim&&old.position()<target){dropped++;continue;}
  next.println(line);
 }
 if(old)old.close();next.println(payload);next.close();
 if(!LittleFS.rename("/queue.tmp","/queue.jsonl"))Serial.println("Queue replace failed");
}
bool flushQueue(){
 File old=LittleFS.open("/queue.jsonl","r");if(!old)return false;
 File next=LittleFS.open("/queue.tmp","w");if(!next){old.close();return false;}
 bool failed=false;int sent=0;
 while(old.available()){
  button();String line=old.readStringUntil('\n');if(!line.length())continue;
  if(!failed&&sent<8&&request("/api/portable/scan",&line)){sent++;continue;}
  failed=true;next.println(line);
 }
 old.close();next.close();LittleFS.rename("/queue.tmp","/queue.jsonl");
 Serial.printf("Uploaded %d queued samples\n",sent);return sent>0;
}
void survey(){
 ledMode=LedMode::Zigbee;WiFi.mode(WIFI_OFF);waitResponsive(250);
 JsonDocument doc;doc["device_id"]=DEVICE_ID;doc["boot_id"]=bootId;doc["seq"]=seq++;
 String captureLocation=location,captureSession=session;
 uint32_t start=millis();double t=timestamp();std::array<uint8_t,16> energy;
 bool ok=scanRadio(energy);uint32_t duration=millis()-start;
 doc["clock_valid"]=t>1700000000;if(t>1700000000)doc["captured_at"]=t+duration/2000.0;else doc["captured_at"]=nullptr;
 doc["wifi_off_during_zigbee"]=true;doc["zigbee_duration_ms"]=duration;
 doc["location"]=captureLocation;if(captureSession.length())doc["session"]=captureSession;else doc["session"]=nullptr;
 doc["waypoint"]=waypoint;doc["queue_dropped"]=dropped;
 JsonArray channels=doc["channels"].to<JsonArray>();
 if(ok)for(int i=0;i<16;i++){auto c=channels.add<JsonObject>();c["channel"]=11+i;c["raw"]=energy[i];}
 else doc["radio_error"]="CC2652P energy scan did not complete";
 // Active Wi-Fi probe traffic happens only after the Zigbee energy sweep.
 ledMode=LedMode::WifiScan;WiFi.mode(WIFI_STA);WiFi.scanNetworks(true,true,false,120);
 int n;uint32_t scanStart=millis();
 while((n=WiFi.scanComplete())==WIFI_SCAN_RUNNING && millis()-scanStart<8000){button();delay(5);}
 JsonArray wifi=doc["wifi"].to<JsonArray>();
 for(int i=0;i<n&&i<32;i++){
  int channel=WiFi.channel(i);if(channel<1||channel>14)continue;
  auto ap=wifi.add<JsonObject>();ap["ssid"]=WiFi.SSID(i);ap["bssid"]=WiFi.BSSIDstr(i);
  ap["channel"]=channel;ap["rssi"]=WiFi.RSSI(i);ap["security"]=(int)WiFi.encryptionType(i);
  ap["hidden"]=WiFi.SSID(i).isEmpty();ap["width_mhz"]=nullptr;
 }
 WiFi.scanDelete();if(timestamp()>1700000000)doc["wifi_scanned_at"]=timestamp();else doc["wifi_scanned_at"]=nullptr;
 bool connected=connectWifi();if(connected)doc["device_ip"]=WiFi.localIP().toString();
 String payload;serializeJson(doc,payload);queueSample(payload);
 bool uploaded=false;
 if(connected){ledMode=LedMode::Uploading;request("/api/portable/bootstrap");uploaded=flushQueue();}
 Serial.printf("Survey %lu: radio=%s APs=%d WiFi=%s location=%s\n",(unsigned long)(seq-1),ok?"OK":"ERROR",n,connected?"connected":"offline",captureLocation.c_str());
 ledMode=!ok?LedMode::Error:(uploaded?LedMode::Ready:LedMode::Offline);
}
void provisionEvent(arduino_event_t *event){
 switch(event->event_id){
  case ARDUINO_EVENT_PROV_START:Serial.println("BLE_SETUP_READY");break;
  case ARDUINO_EVENT_PROV_CRED_RECV:Serial.println("Wi-Fi credentials received");break;
  case ARDUINO_EVENT_PROV_CRED_FAIL:Serial.println("Wi-Fi connection failed; check phone credentials");break;
  case ARDUINO_EVENT_PROV_CRED_SUCCESS:provisioned=true;prefs.putBool("setup",false);rebootAt=millis()+3000;Serial.println("Wi-Fi credentials accepted; restarting into survey mode");break;
  case ARDUINO_EVENT_PROV_END:if(provisioned){prefs.putBool("setup",false);rebootAt=millis()+1500;}break;
  default:break;
 }
}
void initRadio(){
 pinMode(22,OUTPUT);digitalWrite(22,HIGH);pinMode(15,OUTPUT);digitalWrite(15,LOW);delay(100);digitalWrite(15,HIGH);
 radio.begin(115200,SERIAL_8N1,23,19);
 Serial.println(pingRadio()?"CC2652P ping OK":"CC2652P ping failed; surveys will report errors");
}
void setup(){
 Serial.begin(115200);pinMode(BUTTON,INPUT_PULLUP);pinMode(LED_BLUE,OUTPUT);pinMode(LED_GREEN,OUTPUT);lights(false,false);
 xTaskCreate(ledTask,"status-leds",2048,nullptr,1,nullptr);
 prefs.begin("survey",false);bool force=prefs.getBool("setup",false);
 WiFi.mode(WIFI_STA);wifi_config_t saved{};
 bool configured=esp_wifi_get_config(WIFI_IF_STA,&saved)==ESP_OK && saved.sta.ssid[0]!=0;
 if(force||!configured){
  ledMode=LedMode::Setup;setupMode=true;
  WiFi.mode(WIFI_OFF);initRadio();std::array<uint8_t,16> check;bool valid=scanRadio(check);
  Serial.printf("SELFTEST Zigbee=%s channels=%d",valid?"OK":"ERROR",valid?16:0);
  if(valid)for(auto value:check)Serial.printf(" %u",value);Serial.println();
  WiFi.mode(WIFI_STA);int found=WiFi.scanNetworks(false,true,false,120);
  Serial.printf("SELFTEST WiFi APs=%d\n",found);WiFi.scanDelete();
  setupMode=true;WiFi.onEvent(provisionEvent);
  uint8_t uuid[]={0xb4,0xdf,0x5a,0x1c,0x3f,0x6b,0xf4,0xbf,0xea,0x4a,0x82,0x03,0x04,0x90,0x1a,0x02};
  WiFiProv.beginProvision(NETWORK_PROV_SCHEME_BLE,NETWORK_PROV_SCHEME_HANDLER_FREE_BTDM,NETWORK_PROV_SECURITY_1,PROV_POP,PROV_NAME,nullptr,uuid,force);
  Serial.printf("BLE provisioning service: %s; hold button 3s for setup after provisioning\n",PROV_NAME);return;
 }
 WiFi.mode(WIFI_OFF);
 if(!LittleFS.begin(true,"/littlefs",10,"littlefs")){Serial.println("Filesystem initialization failed");ledMode=LedMode::Error;while(true)waitResponsive(100);}
 bootId=String(esp_random(),HEX)+String(esp_random(),HEX);
 initRadio();
 if(connectWifi())request("/api/portable/bootstrap");
 lastSurvey=millis()-5000;
}
void loop(){button();if(!setupMode&&millis()-lastSurvey>=5000){survey();lastSurvey=millis();}delay(5);}
