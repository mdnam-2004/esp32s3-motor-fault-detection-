#include "web_server.h"
#include "motor_fault_config.h"

#include <string.h>
#include <stdio.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "nvs_flash.h"

static const char *TAG = "WEB_SERVER";

#define WIFI_SSID    "ABC"
#define WIFI_PASS    "123456789"
#define MAX_RETRY    10

motor_status_t g_motor_status = {0};

static int s_retry_num = 0;

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(TAG, "Retrying WiFi connection... (%d/%d)", s_retry_num, MAX_RETRY);
        } else {
            ESP_LOGE(TAG, "Failed to connect to WiFi after %d retries", MAX_RETRY);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Connected! IP: " IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "Dashboard: http://" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
    }
}

void wifi_init_softap(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL, NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Connecting to WiFi SSID: %s ...", WIFI_SSID);
}

static const char DASHBOARD_HTML[] =
    "<!DOCTYPE html>"
    "<html lang=\"vi\">"
    "<head>"
    "<meta charset=\"UTF-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>Motor Fault Detection</title>"
    "<style>"
    "*{margin:0;padding:0;box-sizing:border-box}"
    "body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;"
    "background:#0f0f23;color:#e0e0e0;min-height:100vh;"
    "display:flex;flex-direction:column;align-items:center;padding:20px}"
    "h1{font-size:1.6em;margin-bottom:20px;color:#fff;"
    "text-shadow:0 0 20px rgba(100,200,255,0.3)}"
    ".card{background:linear-gradient(135deg,#1a1a3e,#16213e);"
    "border-radius:16px;padding:24px;margin:10px 0;width:100%;max-width:500px;"
    "box-shadow:0 8px 32px rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.05)}"
    ".status-box{text-align:center;padding:20px;border-radius:12px;"
    "font-size:1.8em;font-weight:bold;margin:10px 0;"
    "transition:all 0.5s ease}"
    ".status-tat{background:linear-gradient(135deg,#064e3b,#065f46);color:#34d399;"
    "box-shadow:0 0 30px rgba(52,211,153,0.2)}"
    ".status-binh{background:linear-gradient(135deg,#78350f,#92400e);color:#fbbf24;"
    "box-shadow:0 0 30px rgba(251,191,36,0.2)}"
    ".status-lech{background:linear-gradient(135deg,#7f1d1d,#991b1b);color:#f87171;"
    "box-shadow:0 0 30px rgba(248,113,113,0.2)}"
    ".prob-row{display:flex;align-items:center;margin:8px 0;gap:10px}"
    ".prob-label{width:100px;font-size:0.9em;color:#94a3b8}"
    ".prob-bar-bg{flex:1;height:24px;background:#1e293b;border-radius:12px;overflow:hidden}"
    ".prob-bar{height:100%;border-radius:12px;transition:width 0.5s ease;"
    "display:flex;align-items:center;justify-content:flex-end;padding-right:8px;"
    "font-size:0.75em;font-weight:bold;color:#fff;min-width:40px}"
    ".bar-tat{background:linear-gradient(90deg,#059669,#34d399)}"
    ".bar-binh{background:linear-gradient(90deg,#d97706,#fbbf24)}"
    ".bar-lech{background:linear-gradient(90deg,#dc2626,#f87171)}"
    ".accel{display:flex;justify-content:space-around;text-align:center;margin-top:10px}"
    ".accel-item{padding:10px}"
    ".accel-val{font-size:1.4em;font-weight:bold;color:#60a5fa}"
    ".accel-lbl{font-size:0.8em;color:#64748b;margin-top:4px}"
    ".info{display:flex;justify-content:space-between;color:#64748b;font-size:0.8em;"
    "margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.05)}"
    ".led-row{display:flex;justify-content:center;gap:20px;margin:15px 0}"
    ".led{width:30px;height:30px;border-radius:50%;opacity:0.2;"
    "transition:all 0.5s ease;border:2px solid rgba(255,255,255,0.1)}"
    ".led-on{opacity:1;box-shadow:0 0 20px currentColor}"
    ".led-green{background:#34d399;color:#34d399}"
    ".led-yellow{background:#fbbf24;color:#fbbf24}"
    ".led-red{background:#f87171;color:#f87171}"
    "</style>"
    "</head>"
    "<body>"
    "<h1>&#9881; Motor Fault Detection</h1>"
    "<div class=\"card\">"
    "<div class=\"led-row\">"
    "<div class=\"led led-green\" id=\"led0\"></div>"
    "<div class=\"led led-yellow\" id=\"led1\"></div>"
    "<div class=\"led led-red\" id=\"led2\"></div>"
    "</div>"
    "<div class=\"status-box\" id=\"status\">Dang khoi dong...</div>"
    "</div>"
    "<div class=\"card\">"
    "<h3 style=\"margin-bottom:12px;color:#94a3b8\">Xac suat</h3>"
    "<div class=\"prob-row\">"
    "<span class=\"prob-label\">&#128994; Tat</span>"
    "<div class=\"prob-bar-bg\"><div class=\"prob-bar bar-tat\" id=\"bar0\" style=\"width:0%\">0%</div></div>"
    "</div>"
    "<div class=\"prob-row\">"
    "<span class=\"prob-label\">&#128993; Binh thuong</span>"
    "<div class=\"prob-bar-bg\"><div class=\"prob-bar bar-binh\" id=\"bar1\" style=\"width:0%\">0%</div></div>"
    "</div>"
    "<div class=\"prob-row\">"
    "<span class=\"prob-label\">&#128308; Lech tam</span>"
    "<div class=\"prob-bar-bg\"><div class=\"prob-bar bar-lech\" id=\"bar2\" style=\"width:0%\">0%</div></div>"
    "</div>"
    "</div>"
    "<div class=\"card\">"
    "<h3 style=\"margin-bottom:12px;color:#94a3b8\">Gia toc ke (g)</h3>"
    "<div class=\"accel\">"
    "<div class=\"accel-item\"><div class=\"accel-val\" id=\"ax\">--</div><div class=\"accel-lbl\">X</div></div>"
    "<div class=\"accel-item\"><div class=\"accel-val\" id=\"ay\">--</div><div class=\"accel-lbl\">Y</div></div>"
    "<div class=\"accel-item\"><div class=\"accel-val\" id=\"az\">--</div><div class=\"accel-lbl\">Z</div></div>"
    "</div>"
    "<div class=\"info\">"
    "<span>Inferences: <b id=\"cnt\">0</b></span>"
    "<span>Auto-refresh: 1s</span>"
    "</div>"
    "</div>"
    "<script>"
    "var names=['Tat','Binh thuong','Lech tam'];"
    "var cls=['status-tat','status-binh','status-lech'];"
    "function upd(){"
    "fetch('/api/status').then(r=>r.json()).then(d=>{"
    "var s=document.getElementById('status');"
    "s.textContent=names[d.class];"
    "s.className='status-box '+cls[d.class];"
    "for(var i=0;i<3;i++){"
    "var p=(d.probs[i]*100).toFixed(1);"
    "var b=document.getElementById('bar'+i);"
    "b.style.width=p+'%';b.textContent=p+'%';"
    "var l=document.getElementById('led'+i);"
    "l.className='led '+(i==0?'led-green':i==1?'led-yellow':'led-red')+(i==d.class?' led-on':'');"
    "}"
    "document.getElementById('ax').textContent=d.ax.toFixed(4);"
    "document.getElementById('ay').textContent=d.ay.toFixed(4);"
    "document.getElementById('az').textContent=d.az.toFixed(4);"
    "document.getElementById('cnt').textContent=d.cnt;"
    "}).catch(e=>{})}"
    "setInterval(upd,1000);upd();"
    "</script>"
    "</body></html>";

static esp_err_t root_get_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, DASHBOARD_HTML, strlen(DASHBOARD_HTML));
    return ESP_OK;
}

static esp_err_t api_status_handler(httpd_req_t *req)
{
    char buf[256];
    int len = snprintf(buf, sizeof(buf),
        "{\"class\":%d,\"probs\":[%.4f,%.4f,%.4f],"
        "\"ax\":%.4f,\"ay\":%.4f,\"az\":%.4f,\"cnt\":%lu}",
        g_motor_status.pred_class,
        g_motor_status.probs[0],
        g_motor_status.probs[1],
        g_motor_status.probs[2],
        g_motor_status.ax,
        g_motor_status.ay,
        g_motor_status.az,
        (unsigned long)g_motor_status.inference_count);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, buf, len);
    return ESP_OK;
}

esp_err_t start_webserver(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.stack_size = 8192;
    httpd_handle_t server = NULL;

    if (httpd_start(&server, &config) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server");
        return ESP_FAIL;
    }

    httpd_uri_t root_uri = {
        .uri       = "/",
        .method    = HTTP_GET,
        .handler   = root_get_handler,
    };
    httpd_register_uri_handler(server, &root_uri);

    httpd_uri_t api_uri = {
        .uri       = "/api/status",
        .method    = HTTP_GET,
        .handler   = api_status_handler,
    };
    httpd_register_uri_handler(server, &api_uri);

    ESP_LOGI(TAG, "HTTP server started on port %d", config.server_port);
    return ESP_OK;
}
