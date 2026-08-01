/*
  Gym Instant Replay — button trigger firmware

  Watches a normally-closed (NF) mushroom button on GPIO4. On the *edge* of a
  press, sends one HTTP POST to the receiver, which asks Frigate to export the
  last 10 minutes of mat footage.

  Wiring:
    Button terminal 1 -> GPIO4
    Button terminal 2 -> GND
    (no polarity - it's just a switch)

  NF contact + INPUT_PULLUP:
    at rest  -> contact closed -> pin pulled to GND -> reads LOW
    pressed  -> contact opens  -> internal pullup wins -> reads HIGH
  So PRESSED_STATE is HIGH. Confirm with PRINT_RAW_STATE below before trusting it.
*/

#include <WiFi.h>
#include <HTTPClient.h>

// ---- EDIT THESE ----
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* RECEIVER_HOST = "192.168.1.50";   // dev machine's / Pi's local IP
const int   RECEIVER_PORT = 5001;             // must match the receiver
const char* SHARED_SECRET = "change-me-to-something-random";  // must match RECEIVER_SECRET
// ---------------------

// Set to true for the first bench test: prints the raw pin reading so you can
// see which way round your button actually behaves. Set back to false after.
const bool PRINT_RAW_STATE = false;

const int BUTTON_PIN = 4;
const int LED_PIN    = 2;      // onboard LED on most WROOM-32 dev boards
const int PRESSED_STATE = HIGH;

const unsigned long DEBOUNCE_MS  = 50;     // mechanical bounce settling
const unsigned long COOLDOWN_MS  = 30000;  // matches COOLDOWN_SECONDS on the receiver
const unsigned long HTTP_TIMEOUT = 8000;

int lastStableState = !PRESSED_STATE;
int lastReading     = !PRESSED_STATE;
unsigned long lastChangeMs = 0;
unsigned long lastTriggerMs = 0;
unsigned long lastWifiAttemptMs = 0;

void blink(int times, int onMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(onMs);
    digitalWrite(LED_PIN, LOW);
    delay(onMs);
  }
}

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi");
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);            // keeps latency low; costs battery
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected, IP: ");
    Serial.println(WiFi.localIP());
    blink(2, 80);
  } else {
    Serial.println("Wi-Fi connect timed out, will retry");
  }
}

void sendTrigger() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi down, cannot send trigger");
    blink(5, 60);
    return;
  }

  WiFiClient client;
  HTTPClient http;
  String url = String("http://") + RECEIVER_HOST + ":" + RECEIVER_PORT + "/save-clip";

  http.setTimeout(HTTP_TIMEOUT);
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Auth-Token", SHARED_SECRET);

  int code = http.POST("{}");
  Serial.print("Trigger sent, response: ");
  Serial.println(code);
  Serial.println(http.getString());
  http.end();

  if (code == 202) {
    blink(1, 400);            // one long blink = clip saved
  } else if (code == 429) {
    blink(2, 150);            // still in cooldown, ignored
  } else {
    blink(5, 60);             // something's wrong (401? receiver down?)
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  delay(200);

  lastStableState = digitalRead(BUTTON_PIN);
  lastReading = lastStableState;
  Serial.print("Boot pin state: ");
  Serial.println(lastStableState == HIGH ? "HIGH" : "LOW");

  connectWiFi();
}

void loop() {
  int reading = digitalRead(BUTTON_PIN);

  if (PRINT_RAW_STATE) {
    Serial.println(reading == HIGH ? "HIGH" : "LOW");
    delay(250);
    return;
  }

  if (reading != lastReading) {
    lastReading = reading;
    lastChangeMs = millis();
  }

  // Only act on the transition into the pressed state, once it's stable.
  // (The old code fired on the *level*, so holding the button re-triggered
  // every 800ms.)
  if (millis() - lastChangeMs > DEBOUNCE_MS && reading != lastStableState) {
    lastStableState = reading;

    if (reading == PRESSED_STATE) {
      if (lastTriggerMs == 0 || millis() - lastTriggerMs > COOLDOWN_MS) {
        Serial.println("Button pressed!");
        lastTriggerMs = millis();
        sendTrigger();
      } else {
        Serial.println("Press ignored (cooldown)");
        blink(2, 150);
      }
    }
  }

  // Non-blocking reconnect, retried at most every 10s.
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiAttemptMs > 10000) {
    lastWifiAttemptMs = millis();
    connectWiFi();
  }

  delay(10);
}
