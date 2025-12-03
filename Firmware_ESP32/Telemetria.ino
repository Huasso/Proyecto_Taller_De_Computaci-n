#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "SparkFun_SHTC3.h" // Usando tu sensor RAK1901

// --- CREDENCIALES ---
const char* ssid = "AndroidAP0893";
const char* password = "ullui423";

// --- SERVIDOR AWS ---
// Cambia esto por tu IP Elástica y el puerto nuevo (5000)
String serverUrl = "http://184.72.175.7:5000/api/sensor"; 

SHTC3 mySensor;

#define LED_VERDE 12
#define LED_AZUL 2

unsigned long lastTime = 0;
unsigned long timerDelay = 2000; // Enviar cada 2 segundos

void setup() {
  Serial.begin(115200);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AZUL, OUTPUT);

  Wire.begin();
  if(mySensor.begin() != SHTC3_Status_Nominal){
    Serial.println("Error sensor SHTC3");
    while(1);
  }

  WiFi.begin(ssid, password);
  Serial.print("Conectando");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println(" Conectado!");
}

void loop() {
  if ((millis() - lastTime) > timerDelay) {
    if(WiFi.status() == WL_CONNECTED){
      
      digitalWrite(LED_VERDE, HIGH);
      mySensor.update();
      float t = mySensor.toDegC();
      float h = mySensor.toPercent();
      digitalWrite(LED_VERDE, LOW);

      // Crear JSON
      String json = "{";
      json += "\"temperatura\": " + String(t) + ",";
      json += "\"humedad\": " + String(h) + ",";
      json += "\"nodo\": \"ESP32_Campo_01\"";
      json += "}";

      // Enviar POST
      digitalWrite(LED_AZUL, HIGH);
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");
      int response = http.POST(json);
      
      Serial.printf("T: %.1f H: %.1f -> Resp: %d\n", t, h, response);
      
      http.end();
      digitalWrite(LED_AZUL, LOW);
    }
    lastTime = millis();
  }
}