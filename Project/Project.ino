#include <WiFiS3.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define trigPin 9
#define echoPin 10
#define buzzerPin 7

LiquidCrystal_I2C lcd(0x27,16,2);

// WiFi
const char* ssid = "Roshan";
const char* password = "Gauss121";

// ThingSpeak
const char* server = "api.thingspeak.com";
String writeAPI = "W1YNBIV22TJWBTXZ";
String readAPI  = "A2TGLX8TSI4UBU85";
String channelID = "3308540";

WiFiClient client;

long duration;
int distance;
int vehicleCount = 0;

bool carDetected = false;
bool paymentDone = false;

// 🔊 Beeps
void shortBeep() {
  digitalWrite(buzzerPin, HIGH);
  delay(150);
  digitalWrite(buzzerPin, LOW);
}

void doubleBeep() {
  for(int i=0;i<2;i++){
    digitalWrite(buzzerPin, HIGH);
    delay(150);
    digitalWrite(buzzerPin, LOW);
    delay(150);
  }
}

void setup() {
  Serial.begin(9600);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(buzzerPin, OUTPUT);

  lcd.init();
  lcd.backlight();

  lcd.print("Connecting WiFi");

  // Connect WiFi
  while (WiFi.begin(ssid, password) != WL_CONNECTED) {
    delay(2000);
    lcd.clear();
    lcd.print("Retry WiFi...");
  }

  lcd.clear();
  lcd.print("WiFi Connected");
  delay(2000);

  lcd.clear();
  lcd.print("Waiting for car");
}

void loop() {

  // Measure distance
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH, 30000);

  if(duration == 0){
    delay(100);
    return;
  }

  distance = duration * 0.034 / 2;

  Serial.println(distance);

  // 🚗 Detect car
  if(distance > 2 && distance < 10 && !carDetected){

    shortBeep();

    carDetected = true;
    paymentDone = false;

    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("Vehicle Found");

    lcd.setCursor(0,1);
    lcd.print("Sending Tx...");

    vehicleCount++;
    sendCarDetected(vehicleCount); // field1=1, field3=count
  }

  // ☁️ Check payment
  if(carDetected && !paymentDone){

    int payment = readFromThingSpeak();

    Serial.print("Payment: ");
    Serial.println(payment);

    if(payment == 1){

      paymentDone = true;

      doubleBeep();

      int aiDecision = readAIDecision(); // field4

      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Cloud Verified");

      lcd.setCursor(0,1);
      if(aiDecision == 1){
        lcd.print("Lot: BUSY");
      } else {
        lcd.print("Parking Allowed");
      }
    }
  }

  // 🔁 Reset when car leaves
  if(distance > 15 && carDetected && paymentDone){

    lcd.clear();
    lcd.print("Waiting for car");

    carDetected = false;
    paymentDone = false;

    sendToThingSpeakReset(); // reset field1, field2
  }

  delay(2000); // ThingSpeak delay
}

// 📤 Send field1=1 and field3=vehicleCount on car detection
void sendCarDetected(int count) {

  if (client.connect(server, 80)) {

    String url = "/update?api_key=" + writeAPI + "&field1=1&field3=" + String(count);

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + server + "\r\n" +
                 "Connection: close\r\n\r\n");

    client.stop();
  }
}

// 📤 Reset field1 and field2
void sendToThingSpeakReset() {

  if (client.connect(server, 80)) {

    String url = "/update?api_key=" + writeAPI + "&field1=0&field2=0";

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + server + "\r\n" +
                 "Connection: close\r\n\r\n");

    client.stop();
  }
}

// 📥 Read field4 (AI decision: 1=Busy, 0=Free)
int readAIDecision() {

  if (client.connect(server, 80)) {

    String url = "/channels/" + channelID + "/fields/4/last.txt?api_key=" + readAPI;

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + server + "\r\n" +
                 "Connection: close\r\n\r\n");

    delay(1500);

    String response = "";
    while(client.available()){
      char c = client.read();
      response += c;
    }

    client.stop();

    int index = response.lastIndexOf("\n");
    String valueStr = response.substring(index + 1);
    valueStr.trim();
    return valueStr.toInt();
  }

  return 0;
}

// 📥 Read Field2
int readFromThingSpeak() {

  if (client.connect(server, 80)) {

    String url = "/channels/" + channelID + "/fields/2/last.txt?api_key=" + readAPI;

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + server + "\r\n" +
                 "Connection: close\r\n\r\n");

    delay(1500);

    String response = "";

    while(client.available()){
      char c = client.read();
      response += c;
    }

    client.stop();

    // Extract value
    int index = response.lastIndexOf("\n");
    String valueStr = response.substring(index + 1);
    valueStr.trim();

    return valueStr.toInt();
  }

  return 0;
}